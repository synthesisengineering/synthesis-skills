# Decision packet: passages replaced by the v5 script pass (M3) and since, through 2.5.0

Read this only to review what a change replaced. The passages below are no longer instructions; they are kept
word for word so the reasoning stays readable (ruling D8). Newest first: the 2.5.0 rewrite to the D8 standard,
then the M3 passages and the later replacements of 2.0.1 and 2.1.0.

Lines the 2.0.0 prose carried (from the 1.8.0 SKILL.md and reference files) that stopped
describing the scripts when they were slimmed on 2026-10-05. Each passage is verbatim, under
a heading that says what it was and why it went. The scripts these lines describe are
readable at any time with `git show origin/main:skills/synthesis-decision-packet/scripts/<name>`.

Contents:
- Retired in 2.5.0, the rewrite to the D8 standard: why each part of SKILL.md changed, then the 2.4.0
  SKILL.md word for word
- Claimed provenance (`--provenance`) and input digests in the record (verdict: SLIM, drop claimed-provenance fields)
- Legacy unbound summaries (`--legacy-unbound`) (verdict: SLIM, drop legacy-format parsing)
- `-o` preserving existing bytes (changed: `-o` is a working copy)
- Input-file custody for spec files (verdict: SLIM, drop input-file custody)
- The context doctor's `skill-outputs` check (the check moved; the marker stayed)
- Retiring historical interfaces through `context_edit.py` (replaced by `carry_forward.py`)
- Test file names (tests moved to `tests/`)
- The worked example's rulings file before M3
- The handoff queue (`handoff.py`, replaced by `synthesis msg` in v5)
- The context doctor in binding rule 9 (the check is `synthesis doctor`'s)
- A sentence in "When to use it" that restated binding rule 7 (2.1.0)

## Retired in 2.5.0: the rewrite to the D8 standard

2.5.0 rewrote SKILL.md to the repository's rewrite standard, `docs/skill-writing.md` (writing rules W1 to
W19). Every rule's new place is in [coverage-map.md](coverage-map.md). A passage moved word for word to another
file is recorded there; the whole 2.4.0 SKILL.md is below all the same, so every word of it stays readable in
one place. The references keep their text; what they gained (When to use it and a changelog entry in
background.md, two contents lists) is in the coverage map.

### SKILL.md

Why each part changed:

- **Opening paragraphs.** The first, the origin measurement, is the story behind the skill (format rule 12),
  and its words already stand in background.md's "The origin measurement", so it left SKILL.md (W19). One
  sentence saying what the skill is for takes its place (format rule 2). The second, "The property to preserve
  above all others", is kept word for word without its bold (W13).
- **The line above rule 1.** "Rules 1 to 6 are the six load-bearing properties in their original order, so "the
  sixth load-bearing property" still resolves; new rules are appended." was a note on numbering; W6 now keeps
  every skill's numbers, rules 1 to 6 keep their order, and authoring.md's contents names them as the six
  properties. In its place, a new line (W8, format rule 11) says the rules hold against a contrary request and
  how to answer one, as the skill's absolutes already held: "never pre-select it", "never hand-author rows or
  hand-edit generator output", `authorization.granted: false`, "only a recorded ruling closes one".
- **Binding rules 1 to 15.** Each rewritten to W5 (the action as the bold head, then the scope, the reason and,
  where the skill states one, the stop) and made complete on its own (W2), from the skill's own text. Rule 1
  names its four parts and the blind-row exception, from authoring.md and When NOT to use it. Rules 2 to 6 take
  their reasons from authoring.md's six properties; rule 5 also says that the principal's own wording is read as
  text and not recorded, from filing-and-authority.md, and rule 6 names both filing commands with `--file-into`.
  Rule 9 says what to do instead of a hand edit and what the doctor flags. Rule 10 names the `disagreement` and
  `prior_position` blocks. Rule 11 names its check, from enforcement.md's two fixtures (format rule 14). Rule 13
  names the failure to avoid, a summary and a link (W12). Rule 14 names the narrative sources that close nothing.
  Rule 15 keeps every item, says why in its head, and names the Codex sentence's scope, any question for the
  principal, with "or a filed packet" from authoring.md.
- **Binding rule 7.** It sent the model to the decision-ownership contract in synthesis-thinking-framework, which
  an evaluation harness that opens only this skill's files cannot read; the B1 baseline report found that for
  code-planning's link to the same file. The rule now states the contract's classes itself (W2), and takes the
  stop it had in When to use it, "Honor an explicit supervised review request".
- **Binding rule 8.** At the pinned baseline (v5.0.14) Opus with the skill passed 5 of its 6 checks. Every element
  is kept and each is named as the author meets it in the spec (W14): a plain label with an internal ID only as a
  chip, context saying what the thing is in the reader's words, both sides of `impact`, never a bare Yes or No,
  a one-clause gloss; it says what `--strict-reader` refuses, and gives the 0-of-15 measurement as its reason,
  stated as what goes wrong (format rule 12).
- **Binding rule 12.** The weakest rule at the pinned baseline: on dp-11 Opus with the skill passed 0 of 2.
  The rule now names its trigger as the model meets it, acting on any chosen row, such as a deletion, deploy,
  send or spend (W7, W14), says why a ruling cannot authorize (anyone can paste a summary, from
  filing-and-authority.md), names the checks and where they are made (the principal's authority, the current
  scope and the exact target, with the principal or another authentic source), and says what goes ahead without
  a new confirmation: a grant already given, within its scope, from When to use it. No capitals or stronger
  wording were added (W10), and no near-miss sentence, since no case has shown one (W15).
- **Contents.** Shorter link text and descriptions, so the rules fit with the room W19 leaves under 8,000 bytes;
  every reference keeps a line saying when to read it, coverage-map.md and preserved.md share one, and the
  sections line names the one section left below.
- **When to use it.** Moved word for word to background.md, its link one folder deeper; rules 7 and 12 state its
  first paragraph, and the opening paragraph and When NOT to use it carry its scope.
- **When NOT to use it.** Kept word for word.
- **Use.** The command block stands word for word in filing-and-authority.md's Use section, which Contents names
  for every command and what it prints; rules 6, 9 and 14 name each script. With every binding rule complete on
  its own, SKILL.md would otherwise have run past the room W19 leaves, and format rule 3 moves whole passages
  rather than condensing them.

The 2.4.0 SKILL.md, verbatim:

````markdown
---
name: synthesis-decision-packet
description: "Collect five or more parallel decisions from a principal in one sitting: a self-contained HTML packet with a recommendation per row, consequence-labeled buttons, notes and a paste-back summary, filed in the project. Use when a review, migration, upgrade, triage or backlog pass needs rulings."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.4.0"
  format: v5
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  category: core
---

# Decision Packet

When N unresolved decisions belong to the principal, collecting them one at a time
scales poorly. The measurement that produced this skill is blunt: **26 rounds of per-item
conversation produced 0 of 30 decisions. One packet produced 30 of 30, in one pass, in one
paste.**

**The property to preserve above all others: the principal's cost scales with the number of
*sittings*, not the number of *items*.**

## Binding rules

Rules 1 to 6 are the six load-bearing properties in their original order, so "the sixth load-bearing property" still resolves; new rules are appended.

1. **Self-contained rows:** item, recommendation, reasoning, link. The principal never leaves the packet to decide.
2. **Mark the recommendation on the control; never pre-select it.** A packet that opens decided reports decisions nobody made.
3. **A free-text note box on every row,** beside the buttons. Never force the principal into your option set.
4. **Local persistence keyed by exact spec and item.** A change anywhere in the spec starts fresh choices.
5. **The packet generates the paste-able summary,** so the person never composes the structure.
6. **File in the owning project's `resources/artifacts/`, never only as a chat artifact:** `build_packet.py --file-into` files spec and page; `record_rulings.py` files the rulings.
7. **Only decisions that belong to the principal.** Execute constraint-determined choices and resolve delegated technical choices yourself.
8. **The reader contract: a packet is a stranger-read document.** Name the `audience`, use plain labels, state `impact` both ways, label options by what pressing them does, gloss terms of art, and build every packet for a principal with `--strict-reader`.
9. **Generate from a data array; never hand-author rows or hand-edit generator output.** `synthesis doctor` flags unverifiable packet pages in its *decision packets* check.
10. **Surface disagreement and prior positions with exact sources; never converge first,** and recommend against your own prior work where that is true.
11. **Open every generated packet before handing it over.** Both permanent defects were found by loading the page, not reading the source.
12. **A recorded ruling authorizes nothing** (`authorization.granted: false`). The action owner checks principal, scope and exact target before acting.
13. **Show the complete material** for correspondence, code, images, media or documents in `review_assets`; external references are never fetched.
14. **Unanswered decisions carry forward by exact id; only a recorded ruling closes one.** `carry_forward.py` writes the successor spec, and refuses a reconciliation with missing, extra or duplicate ids or a narrative "answered" with no ruling recorded against the exact spec.
15. **Keep the reading path short:** changes against the reviewed `baseline`, material once, messages as their words, wire copies as `reference`, settled items in `handled`. On Codex, ask in the final reply, never only in a question card.

## Contents

- [references/authoring.md](references/authoring.md): the six properties in full, review material, prior positions, content requirements, the reader contract, a comfortable reading path. Read it before writing any spec.
- [references/filing-and-authority.md](references/filing-and-authority.md): the commands and what they print, filing, recording rulings, schema-2 records, action authority, carrying unanswered decisions forward. Read it when generating, filing, recording or replacing a packet.
- [references/enforcement.md](references/enforcement.md): integrity markers, what the generator refuses, the two permanent fixtures. Read it when a build is refused, the doctor flags a packet, or before changing the generator.
- [references/review-assets.md](references/review-assets.md): the review-asset contract. Read it before constructing `review_assets`.
- [references/worked-example.md](references/worked-example.md): a complete spec, the filed copies, the paste and its rulings file. Read it before your first packet.
- [references/background.md](references/background.md): the origin measurement, relationship to autopilot, adversarial review and board messages between agents (`synthesis msg`), changelog, related skills. Read it when choosing between this skill and a neighbor.
- [references/coverage-map.md](references/coverage-map.md): where the 1.8.0 text and old scripts now live. Read it when tracing an old rule or command.
- [references/preserved.md](references/preserved.md): lines the v5 script pass replaced, verbatim, with reasons. Read it for the earlier wording.
- When to use it, When NOT to use it, Use: below.

## When to use it

First apply [decision ownership](../synthesis-thinking-framework/references/decision-ownership.md).
Packets collect decisions that actually belong to the principal (binding rule 7).
Honor an explicit supervised review request.
Existing user grants remain usable within their scope; the new record format does
not require the user to repeat them.

Load when you owe your principal **five or more parallel decisions of the same shape**, each
needing supporting context, where you have a defensible recommendation per item and the decisions
matter enough to deserve attention but are too numerous for per-item conversation.

Natural fits: review findings to fix or waive · dependency bumps to take or hold · drafts to
publish, edit, or kill · files to migrate or leave · flaky tests to quarantine or fix · features
to build now, later, or never · candidates to advance on a defined rubric.

## When NOT to use it

- **Fewer than about five decisions.** Just ask in chat. The generator refuses below five without
  `--allow-small`.
- **The decisions are not parallel in shape.** A packet of unlike questions is a form, and a form
  is worse than a conversation.
- **You have no recommendation per item.** Then the packet is a questionnaire and *your analysis
  is not finished*. Do the analysis. The generator refuses a row that recommends nothing,
  unless it is blind.

- **A deadline whose miss cannot be undone.** It is never one row among many: it leads the day
  plan in its own section (synthesis-daily-rituals) and closes only on evidence. The generator
  refuses a row tagged `critical`.

The failure mode of a good pattern is over-application. These four limits are the skill.

## Use

```bash
python3 scripts/build_packet.py --schema              # the spec format
python3 scripts/build_packet.py spec.json -o packet.html --strict-reader
python3 scripts/build_packet.py spec.json --stdout    # to a pipe
python3 scripts/build_packet.py spec.json --strict-reader \
    --file-into PROJECT/resources/artifacts/         # + <date>-<slug>-spec.json, <date>-<slug>.html
python3 scripts/record_rulings.py paste.txt \
    --spec PROJECT/resources/artifacts/<date>-<slug>-spec.json \
    --file-into PROJECT/resources/artifacts/         # -> <date>-<slug>-rulings.json
python3 scripts/carry_forward.py PROJECT/resources/artifacts/<date>-<slug>-spec.json \
    --successor next-spec.json                       # the unanswered rows, ids unchanged
python3 scripts/carry_forward.py PROJECT/resources/artifacts/<date>-<slug>-spec.json \
    --check reconciliation.json                      # every id answered or carried, once
```

What each command prints: [references/filing-and-authority.md](references/filing-and-authority.md).
````

## Claimed provenance and input digests in the record

Why it went: the evaluation's verdict for `record_rulings.py` was SLIM, dropping
claimed-provenance fields. A provenance file recorded claims the tool could never verify,
and the file, spec-file and summary digests were custody that nothing read. Every record
still says `authorization.granted: false` and `authentication: unverified`. From
references/filing-and-authority.md (originally the 1.8.0 SKILL.md, section Use):

`note`. They add the complete canonical spec SHA-256, actual filed-spec byte
digest, summary digest, claimed provenance and an explicit non-authorizing status.

From the section "Provenance and action authority" (now "Action authority"):

## Provenance and action authority

When the trusted conversation supplies attribution, pass `--provenance FILE` with
exactly five nonempty strings: `principal`, `source_ref`, `received_at` (an ISO
timestamp with timezone), `scope`, and `authority_ref`. The recorder preserves
these claims and the provenance-file digest as `claimed-unverified`; it cannot
verify an identity merely because a local file names one. Missing provenance stays
`unattributed-paste`, with unknown fields explicit. `ruled_on` is the supplied
record date, not proof of when the principal acted.

From references/worked-example.md, the paragraph under the rulings file:

The unknown provenance and `authorization.granted: false` fields are deliberate: this
synthetic record does not authenticate a principal. A real action owner must verify the
trusted user instruction and exact operation. The format does not revoke grants already
supplied by the user. Historical unbound summaries remain readable through
`--legacy-unbound --stdout` without rewriting their records.

## Legacy unbound summaries

Why it went: the verdict dropped legacy-format parsing. A summary without the binding line
cannot become a record; the recorder says so and names the remedy (rebuild the packet from
its spec). From references/filing-and-authority.md, section "Provenance and action authority":

Historical text remains readable with `--legacy-unbound --stdout`; historical
records remain untouched. This read does not produce a new bound filing. An old
record's lack of a schema-2 binding neither authenticates it nor erases authority
already supplied in a trusted user instruction. Resolve that authority through
its actual owner and source.

## `-o` preserving existing bytes

Why it changed: the filed copies under `--file-into` are the record and are never replaced;
`-o` is the agent's working copy, so a rebuild after a spec fix overwrites it instead of
being refused. From references/filing-and-authority.md, section Use:

Identical imports are idempotent. A changed response receives a distinct filename;
there is no destructive `--replace`. Preserve and commit the spec, page, original
response and recorded versions in the owning project. An explicit `--out` path also
preserves existing bytes; give a revised page a new path or use versioned filing.

## Input-file custody for spec files

Why it went: the verdict for `build_packet.py` dropped input-file custody (the stable
regular-file identity checks while reading). The 8 MiB ceiling stays. From
references/review-assets.md, section "Binary assets":

All decoded review material together is limited to 4 MiB. Spec files are
limited to 8 MiB and must be stable regular files; symlink files, special nodes,
late replacement and oversized inputs are refused. Standard input has the same
byte ceiling; its caller owns stream lifetime. The final generated HTML also
has an 8 MiB ceiling, matching the existing context-doctor reader. JSON escaping

## The context doctor's `skill-outputs` check

Why it changed: in v5 the marker is read by `synthesis doctor` (its "decision packets"
check, which reports a page with no marker or a marker that disagrees with its embedded
spec). The marker's form is unchanged. From references/enforcement.md, section
"Enforcement (v1.5.0)":

`record_rulings.py` validates the current spec and every selected value before
filing. The context doctor's existing `skill-outputs` check fails
any packet page under a project's `resources/artifacts/` that is not
verifiable generator output: unmarked with no filed rulings is a defect
(rebuild with the generator or remove it); a marker that disagrees with
the embedded spec is a defect (never hand-edit generator output); a
closed record (unmarked but ruled) warns. The rule ships on every
machine with install, upgrade, and doctor — it is not a local note.

## Retiring historical interfaces through `context_edit.py`

Why it went: the custody, archive and multi-file transaction it named belonged to the
succession machinery of the context-lifecycle skill. The rule it served (every unanswered
decision survives by exact id; a filename or a narrative does not establish closure) is now
`carry_forward.py` in this skill. The generator no longer refuses to file a retired spec.
From references/filing-and-authority.md (the link path as adjusted in 2.0.0):

## Retiring historical interfaces

Read [artifact succession](../../synthesis-context-lifecycle/references/artifact-succession.md)
before retiring a packet or reconciling transferred decisions. `context_edit.py`
owns exact-byte custody and the existing multi-file transaction; the packet owner
refuses filing a retired exact spec or equivalent payload as a new live interface.
A rulings filename does not establish closure. Preserve actual answers and every
unanswered or unverified obligation; archive and transfer grant no new authority.

## Test file names

Why they changed: tests moved from `scripts/` to `tests/` with unique names. From
references/enforcement.md, section "Two defects that are permanent fixtures":

Both shipped in the reference implementation; one reached the principal in real use. They are
regression-tested in `scripts/test_build_packet.py`.

From references/worked-example.md:

`scripts/test_build_packet.py` exercises this exact example through the recorder CLI.

From references/review-assets.md, section "Authority and operational boundaries" (the
keyboard and download fixtures drove a real browser and went with the old tests):

The generation, DOM, keyboard, persistence, download and copy-failure fixtures
use only synthetic material. Their passing results prove transport and reader

## The worked example's rulings file before M3

Why it changed: the record no longer carries the spec-file digest, the summary digest or
claimed provenance; it names the spec file and says whether storage was blocked. The
2.0.0 file, from references/worked-example.md:

```json
{
  "packet": "Dependency sweep — Q3",
  "decided": 2,
  "total": 2,
  "rulings": [
    {
      "id": "D-01",
      "label": "cryptography 41.0.3 → 43.0.1",
      "choice_value": "take",
      "choice_label": "Upgrade to the new version",
      "took_recommendation": true,
      "accepted_in_bulk": false,
      "recommended_label": "Upgrade to the new version",
      "note": null
    },
    {
      "id": "D-02",
      "label": "pydantic 1.10 → 2.9",
      "choice_value": "take",
      "choice_label": "Upgrade to the new version",
      "took_recommendation": false,
      "accepted_in_bulk": false,
      "recommended_label": "Keep the current version this quarter",
      "note": "Do it now behind a branch. Reviewer B is right about the support window and\nI would rather eat the conflict than the deprecation."
    }
  ],
  "schema_version": 2,
  "binding": {
    "status": "spec-bound",
    "spec_sha256": "1083c7b8660aa75fadec429cb038ebd79f379098cba1160f35c806993404ec15"
  },
  "ruled_on": "2026-09-14",
  "spec": {
    "file": "2026-09-14-dependency-sweep-q3-spec.json",
    "file_sha256": "1083c7b8660aa75fadec429cb038ebd79f379098cba1160f35c806993404ec15",
    "canonical_sha256": "1083c7b8660aa75fadec429cb038ebd79f379098cba1160f35c806993404ec15"
  },
  "summary_sha256": "eb862170b00ae2f1b67b37f9d13dad7ee4147205ef4c35ebf3f4ae6c6dd05b07",
  "provenance": {
    "status": "unattributed-paste",
    "authority_ref": null,
    "principal": null,
    "received_at": null,
    "scope": null,
    "source_ref": null
  },
  "authorization": {
    "granted": false,
    "authentication": "unverified",
    "owner": "existing action owner must verify trusted authority and exact operation"
  }
}
```

## The handoff queue

Replaced in 2.0.1 (2026-10-05, final v5 sweep): v5 removed
`synthesis-project-management/scripts/handoff.py` (verdict: REPLACE by `synthesis msg` with a
brief file). The relationship the lines described is unchanged: messages move work between
agents, the decision packet moves decisions between agent and principal.

SKILL.md, Contents, the background.md line (2.0.0):

```text
- [references/background.md](references/background.md): the origin measurement, relationship to autopilot, adversarial review and the handoff queue (`synthesis-project-management/scripts/handoff.py`), changelog, related skills. Read it when choosing between this skill and a neighbor.
```

references/background.md, Relationship to adjacent skills (2.0.0, verbatim from 1.8.0):

```text
- **The handoff queue** (`synthesis-project-management/scripts/handoff.py`) moves work *between
  agents*. The decision packet moves decisions *between agent and principal*. Together they are
  the two directions that stop routing everything through a person as the transport layer.
```

## The context doctor in binding rule 9

Replaced in 2.0.1 (2026-10-05, final v5 sweep): the packet check is `synthesis doctor`'s
*decision packets* check (`check_packets` in `synthesis/doctor.py`), as
[enforcement.md](enforcement.md) already said; v5's `context_doctor.py` has no packet check.
The 2.0.0 line, verbatim:

```text
9. **Generate from a data array; never hand-author rows or hand-edit generator output.** The context doctor fails unverifiable packet pages.
```

## A sentence in "When to use it" that restated binding rule 7

Replaced in 2.1.0 (2026-10-13): binding rule 7 states the same rule ("Execute constraint-determined
choices and resolve delegated technical choices yourself"), and the line made room for binding
rule 15 within the 8,000-byte limit. The 2.0.1 lines, verbatim:

```text
Packets collect decisions that actually belong to the principal. Execute choices
already determined by constraints and resolve delegated technical choices without
putting them back into a questionnaire. Honor an explicit supervised review request.
```

