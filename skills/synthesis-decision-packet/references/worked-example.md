# Worked example — a dependency-upgrade packet

A small, complete spec and what it produces. Copy it, replace the rows, generate.

## The situation

A quarterly dependency sweep on a service turns up eleven packages with available upgrades. Some
are security patches, some are majors with breaking changes, one is a transitive pin someone added
in a hurry. Each needs the same decision — take it, hold it, or pin it deliberately — and each
needs different context to decide. Eleven per-item messages would cost eleven round-trips and
would still leave the agent reassembling the answers out of prose.

## The spec

```json
{
  "title": "Dependency sweep — Q3",
  "subtitle": "11 packages with upgrades available",
  "intro": "Take, hold, or pin each. Pinning asks for a reason in the note box.",
  "storage_key": "dep-sweep-2026-q3",
  "options": [
    {"value": "take",  "label": "Take it",  "tone": "ok"},
    {"value": "hold",  "label": "Hold",     "tone": "warn"},
    {"value": "pin",   "label": "Pin",      "tone": "muted"}
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
      "reasoning": "Take it. Security patch, no call-site changes, and our own tests cover the two functions involved.",
      "recommendation": "take",
      "links": [{"label": "advisory", "href": "https://example.invalid/advisory"}]
    },
    {
      "id": "D-02",
      "label": "pydantic 1.10 → 2.9",
      "severity": "medium",
      "tags": ["breaking"],
      "context": "Major. Validators change signature; 34 models across 9 modules use the v1 style.",
      "reasoning": "Hold. The upgrade is right eventually, but it is a week of work and it lands in the same files as the launch changes. Take it after the freeze lifts.",
      "recommendation": "hold",
      "disagreement": {
        "a": {"who": "Reviewer A", "view": "Hold. Two large changes in one file set is how a rollback becomes impossible."},
        "b": {"who": "Reviewer B", "view": "Take it now. v1 loses support in four months and the freeze keeps getting extended."}
      }
    }
  ]
}
```

## Generate it

```bash
python3 scripts/build_packet.py dep-sweep.json -o dep-sweep.html
open dep-sweep.html      # always look at it before handing it over
```

## What comes back

The principal works the rows, clicks, occasionally types, and pastes one message:

```
Dependency sweep — Q3
=====================

D-01  cryptography 41.0.3 → 43.0.1
    -> Take it  (took the recommendation)

D-02  pydantic 1.10 → 2.9
    -> Take it  (OVERRODE: recommended Hold)
    note: Do it now behind a branch. Reviewer B is right about the support window and
          I would rather eat the conflict than the deprecation.

Decided 11 of 11.
```

Three things that make this output useful to the agent that receives it:

- **Overrides are labelled.** `OVERRODE: recommended Hold` tells you your judgment was wrong here
  and, over time, where it is systematically wrong.
- **Undecided rows say so** rather than being silently absent, so a half-finished sitting is
  legible instead of ambiguous.
- **Notes travel with their row**, already associated with the id you need.

## Notes on writing good rows

- **`context` is what the reader needs to judge it.** Not everything you know — what a decision
  turns on. If a row's context is longer than its reasoning, you are probably explaining rather
  than recommending.
- **`reasoning` is why you recommend what you recommend**, in one or two sentences. The packet
  renders it under a bold "Recommendation" lead-in, so do not repeat the word.
- **Reach for `disagreement` whenever two passes genuinely disagreed.** Resolving it first and
  presenting the winner is the single most tempting mistake, and it costs the principal the one
  thing only they can supply.
- **Severity should be visible before the words are read.** Use `high` sparingly or the rail
  stops meaning anything.
