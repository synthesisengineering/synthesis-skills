# Domain review package

Contents:
- What a package is, and what it is not
- Four profiles and seven records
- Checks the reviewer applies (the ten incident shapes)
- Twelve lessons and the acceptance scorecard

A closed review package is one markdown file in the owning project's
`resources/`, beside the findings file, that freezes what is under review before
the first round. It is a record, never a second authority store: the findings
file, the approval owner and the project's session log keep their roles. A
complete package means its structure and current source bytes were checked. It
does not mean observations are true, a person is authenticated, review is
sufficient, or any publication is authorized. The effect owner checks its own
approval at the moment it acts (in v5, the send and deploy guards' approval
codes).

## Four profiles and seven records

Choose editorial, code/control, research, or operations/compliance before work.
Each profile names the planes the matrix must cover:

| Profile | Required planes |
|---|---|
| editorial | principal-objective, claims, attribution, required-content, rendered-content, url-identity, publication |
| code/control | principal-objective, source, tests, security, runtime, recovery, release |
| research | principal-objective, source-universe, provenance, methods, counterevidence, uncertainty |
| operations/compliance | principal-objective, authority, scope, effects, recovery, disclosure, handoff |

The package holds seven kinds of provider-neutral record, each with these fields:

| Record | Fields |
|---|---|
| target | id; domain (the profile); principal objective; files, each with its sha256 or the commit that pins it; planes |
| claim | id; target; plane; text; evidence |
| finding | id; target; its findings-table ID; plane; evidence |
| evidence | id; target; kind (synthetic, source, native or live-observation); producer; method; files; scope |
| decision | id; target; the owner's approval record; target digest; action; approver; evidence |
| handoff | id; target; target digest; reviewer; evidence; links |
| terminal result | id; target; artifact; plane; destination; phase (content, control, platform or publication); status (verified, failed, unverified or not-authorized); evidence; approval |

Identities are unique before anything is aggregated, every cross-reference
resolves inside the package, and each destination keeps its own outcome. A
finding refers to its findings-table ID; a decision refers to its actual owner's
approval record. A record format aids interchange; it grants nothing.

Freeze the full artifact × plane matrix in the review target. Each assigned cell
needs an explicit terminal disposition, including absent evidence. A source
snapshot is not proof its producer works. Native capability and release-history
evidence are different. The reviewer derives load-bearing facts independently;
copied receipts do not establish independence. A handoff identifies the receiver,
not a claim that a listed producer's work is the receiver's observation.

## Checks the reviewer applies

Each check below is a review rule, applied by reading and running things, and
each answers one incident shape (the ten replay shapes of 1.2.1, noted in
brackets). Historical incidents remain private evidence; synthetic replays do
not reclassify original failures.

- **Instruments.** List every Python, JavaScript, C and shell file in the target,
  plus executable files whatever their name. Give each a role (producer,
  validator, test, build or fixture) and a terminal result. An undeclared
  instrument or changed source reopens the package. Listing executes nothing.
- **Content.** Keep source scaffolds, required rendered content, attribution
  directives and actual named-entity presence separate. A source sentence or a
  keyword match is a candidate; it cannot settle an editorial judgment.
- **Calibration.** Require positive and negative controls and keep errors and
  missing runs visible. Uniform failure does not prove the target is defective:
  sixty cases that all fail, controls included, mean the instrument is invalid.
  Only when every control behaves as expected is the check calibrated, and then
  only for its fixtures. [uniform failure of 60 cases]
- **Custody.** Keep durable deletions, each with its proof, separate from
  disposable fixtures and temporary paths. Actual move and delete authority and
  old custody proof belong to their owners. [durable versus disposable paths]
- **Lifecycle.** Never collapse exact-session state, aggregate hygiene,
  communication delivery and continuity into one readiness label. One session
  ready leaves other owners' open work open, and a delivered board message is
  not a finished checkpoint. [exact-session readiness with aggregate open work;
  delivered board message with incomplete continuity]
- **Corpus.** A change in source bytes, population or publication disposition
  invalidates earlier counts and the results built on them; a title or headline
  change also invalidates the unpublished URL-identity plane. [a 455-item corpus
  changed by 30 publications]
- **Publication.** Record each destination's observed bytes separately from the
  approved bytes. Matching bytes grant no authority; bytes that differ from the
  approved ones mean the approval target changed and nothing is authorized,
  however the commit or push went; a destination nobody observed stays
  unverified. Use actual origin and rendered checks, including retired-route
  identity, before a publication result. [mixed automatic and manual destination
  outcomes; approval versus actual bytes]
- **Independence.** The reviewer derives the entire declared universe itself.
  A reviewer that derived part of it has not reviewed the rest, and a copied
  receipt is not an observation. [independently derived reviewer inputs]
- **Links.** Relative links resolve from their actual destination copy, not
  from the author's working directory. [destination-relative handoff links]
- **Saved outputs.** Open the named saved files and record every prior output's
  disposition (retained or deleted, with proof). A named file that is absent
  fails; input parsing cannot prove generated-output attribution. [exact saved
  output with prior custody]

Read sources with bounds. A budget that runs out refuses, never truncates;
large histories go through their archive owner rather than a raised limit; and
truncated data is never treated as complete.

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

The scorecard records principal sittings, rereads, duplicate work, elapsed target
seconds, severity found, repair defects and omitted planes. Missing observations
remain null. No universal superiority, model compliance or token savings follows
from fixture success. Keep executor, reviewer and adjudicator in the current
single skill per the saved packaging decision; split only with new role-confusion
or size evidence showing that packaging is the repair. This package introduces
referenced protocols and typed data, not a redundant review lifecycle engine.
