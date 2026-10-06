# Decision packet: passages replaced by the v5 script pass (M3)

Lines the 2.0.0 prose carried (from the 1.8.0 SKILL.md and reference files) that stopped
describing the scripts when they were slimmed on 2026-10-05. Each passage is verbatim, under
a heading that says what it was and why it went. The scripts these lines describe are
readable at any time with `git show origin/main:skills/synthesis-decision-packet/scripts/<name>`.

Contents:
- Claimed provenance (`--provenance`) and input digests in the record (verdict: SLIM, drop claimed-provenance fields)
- Legacy unbound summaries (`--legacy-unbound`) (verdict: SLIM, drop legacy-format parsing)
- `-o` preserving existing bytes (changed: `-o` is a working copy)
- Input-file custody for spec files (verdict: SLIM, drop input-file custody)
- The context doctor's `skill-outputs` check (the check moved; the marker stayed)
- Retiring historical interfaces through `context_edit.py` (replaced by `carry_forward.py`)
- Test file names (tests moved to `tests/`)
- The worked example's rulings file before M3

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
