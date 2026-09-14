# Worked example — a dependency-upgrade packet

A small, complete spec and what it produces. Copy it, replace the rows, generate, file.

## The situation

A quarterly dependency sweep on a service turns up eleven packages with available upgrades. Some
are security patches, some are majors with breaking changes, one is a transitive pin someone added
in a hurry. Each needs the same decision — upgrade, stay put this quarter, or pin deliberately —
and each needs different context to decide. Eleven per-item messages would cost eleven round-trips
and would still leave the agent reassembling the answers out of prose.

## The spec

Every option label says what pressing the button does. "Take it" / "Hold" / "Pin" would name the
agent's verbs; the principal needs to know what happens to the service. The generator warns on a
bare "Yes" / "No" and `--strict-reader` refuses it.

The spec shown is a two-row excerpt of the eleven-row packet, built with `--allow-small` so the
example stays short; the paste and the rulings file below are what those two rows produce.

```json
{
  "title": "Dependency sweep — Q3",
  "subtitle": "11 packages with upgrades available",
  "intro": "Upgrade, stay on the current version this quarter, or pin. Pinning asks for a reason in the note box.",
  "audience": "The service owner, who has not read the sweep and does not track upstream release notes.",
  "storage_key": "dep-sweep-2026-q3",
  "options": [
    {"value": "take",  "label": "Upgrade to the new version",             "tone": "ok"},
    {"value": "hold",  "label": "Keep the current version this quarter",  "tone": "warn"},
    {"value": "pin",   "label": "Pin the current version and record why", "tone": "muted"}
  ],
  "filters": [
    {"id": "sec",       "label": "Security",        "tags": ["security"]},
    {"id": "breaking",  "label": "Breaking change", "tags": ["breaking"]},
    {"id": "disputed",  "label": "We disagreed",    "disagreement": true},
    {"id": "undecided", "label": "Not yet decided", "undecided": true}
  ],
  "rows": [
    {
      "id": "D-01",
      "label": "cryptography 41.0.3 → 43.0.1",
      "severity": "high",
      "tags": ["security"],
      "context": "Patches a padding-oracle issue in the current pin. No API change on the surface we use.",
      "reasoning": "Upgrade. Security patch, no call-site changes, and our own tests cover the two functions involved.",
      "impact": {
        "accept": "The padding-oracle issue is closed in the next deploy.",
        "decline": "The service keeps shipping with a known, published vulnerability."
      },
      "recommendation": "take",
      "links": [{"label": "advisory", "href": "https://example.invalid/advisory"}]
    },
    {
      "id": "D-02",
      "label": "pydantic 1.10 → 2.9",
      "severity": "medium",
      "tags": ["breaking"],
      "context": "Major. Validators change signature; 34 models across 9 modules use the v1 style.",
      "reasoning": "Keep the current version this quarter. The upgrade is right eventually, but it is a week of work and it lands in the same files as the launch changes. Take it after the freeze lifts.",
      "impact": {
        "accept": "Nothing changes before the launch; the migration is scheduled for the quarter after.",
        "decline": "A week of model rewrites lands in the launch files during the freeze."
      },
      "options": [
        {"value": "take", "label": "Upgrade to the new version", "tone": "ok",
         "consequence": "A week of model rewrites lands in the launch files now, behind a branch."},
        {"value": "hold", "label": "Keep the current version this quarter", "tone": "warn",
         "consequence": "Nothing changes before the launch; v1 support ends in four months."},
        {"value": "pin",  "label": "Pin the current version and record why", "tone": "muted",
         "consequence": "The service stays on v1 past end of support until someone unpins it."}
      ],
      "recommendation": "hold",
      "disagreement": {
        "a": {"who": "Reviewer A", "view": "Stay on the current version. Two large changes in one file set is how a rollback becomes impossible."},
        "b": {"who": "Reviewer B", "view": "Upgrade now. v1 loses support in four months and the freeze keeps getting extended."}
      }
    }
  ]
}
```

D-01 relies on the row's `impact` block: the packet puts `impact.accept` under the recommended
button and `impact.decline` under the other two. D-02 spells out a `consequence` per option
because the three outcomes differ from each other, and "if you don't" would flatten two of them
into one sentence.

## Generate it and file it

```bash
python3 scripts/build_packet.py dep-sweep.json --strict-reader --allow-small \
    -o dep-sweep.html \
    --file-into PROJECT/resources/artifacts/
open dep-sweep.html      # always look at it before handing it over
```

`--allow-small` is there because this excerpt has two rows; the full eleven-row packet builds
without it.

`--file-into` writes `2026-09-14-dependency-sweep-q3-spec.json` and
`2026-09-14-dependency-sweep-q3.html` into the owning project's artifacts directory (the date
is today's; `--date` overrides it). The directory must exist. The page is what the principal
opens; the filed copies are what every other agent on the project can read.

## What comes back

The principal works the rows, clicks, occasionally types, and pastes one message. This is the
exact text the packet's "Copy summary" button produces; a note's own line breaks are kept as
typed:

```
Dependency sweep — Q3
=====================

D-01  cryptography 41.0.3 → 43.0.1
    -> Upgrade to the new version  (took the recommendation)

D-02  pydantic 1.10 → 2.9
    -> Upgrade to the new version  (OVERRODE: recommended Keep the current version this quarter)
    note: Do it now behind a branch. Reviewer B is right about the support window and
I would rather eat the conflict than the deprecation.

Decided 2 of 2.
```

Three things that make this output useful to the agent that receives it:

- **Overrides are labelled.** `OVERRODE: recommended Keep the current version this quarter` tells
  you your judgment was wrong here and, over time, where it is systematically wrong.
- **Undecided rows say so** rather than being silently absent, so a half-finished sitting is
  legible instead of ambiguous.
- **Notes travel with their row**, already associated with the id you need.

## Record the rulings

Save the paste to a file and file it beside the spec and page:

```bash
python3 scripts/record_rulings.py paste.txt --file-into PROJECT/resources/artifacts/
```

That writes `2026-09-14-dependency-sweep-q3-rulings.json`:

```json
{
  "packet": "Dependency sweep — Q3",
  "ruled_on": "2026-09-14",
  "decided": 2,
  "total": 2,
  "rulings": [
    {
      "id": "D-01",
      "label": "cryptography 41.0.3 → 43.0.1",
      "choice_label": "Upgrade to the new version",
      "took_recommendation": true,
      "accepted_in_bulk": false,
      "recommended_label": "Upgrade to the new version",
      "note": null
    },
    {
      "id": "D-02",
      "label": "pydantic 1.10 → 2.9",
      "choice_label": "Upgrade to the new version",
      "took_recommendation": false,
      "accepted_in_bulk": false,
      "recommended_label": "Keep the current version this quarter",
      "note": "Do it now behind a branch. Reviewer B is right about the support window and\nI would rather eat the conflict than the deprecation."
    }
  ]
}
```

The script refuses a paste that is not in the button's format and names the line that failed,
the form it expected there and the text it received; it refuses a paste whose row count
disagrees with its own `Decided n of m.` line; and it keeps an existing rulings file for the
same date and packet unless `--replace` is passed. `scripts/test_build_packet.py` parses the
paste above and compares the result with the rulings JSON above, so this document and the
parser cannot drift apart. Commit the three files with the project so the next session, and
any other agent, reads the decisions from the repository.

## Notes on writing good rows

- **`context` is what the reader needs to judge it.** Not everything you know — what a decision
  turns on. If a row's context is longer than its reasoning, you are probably explaining rather
  than recommending.
- **`reasoning` is why you recommend what you recommend**, in one or two sentences. The packet
  renders it under a bold "Recommendation" lead-in, so do not repeat the word.
- **Labels name outcomes, not verbs.** Read each button as the principal will: "if I press this,
  then what?" If the answer is not in the label, rewrite the label. Two labels that differ only
  in a stopword ("Keep it" / "Keep that") are one label written twice, and an acknowledgement
  padded with one ("Accept it", "Do that") is still an acknowledgement.
- **Title, row labels and option labels are single lines.** The paste prints each on its own
  line and `record_rulings.py` reads it back that way; the generator refuses a line break in
  any of them, so a packet that builds can always be filed.
- **Reach for `disagreement` whenever two passes genuinely disagreed.** Resolving it first and
  presenting the winner is the single most tempting mistake, and it costs the principal the one
  thing only they can supply.
- **Severity should be visible before the words are read.** Use `high` sparingly or the rail
  stops meaning anything.
