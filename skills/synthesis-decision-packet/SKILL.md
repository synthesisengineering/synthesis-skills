---
name: synthesis-decision-packet
description: Collect many parallel decisions from a principal in one sitting instead of one per turn. Generates a self-contained HTML packet — one row per decision carrying the item, the agent's recommendation, the reasoning, and a link — with buttons, a per-row note box, local persistence, and a paste-able summary the principal returns in a single message. Use when you owe five or more decisions of the same shape; when a review, migration, upgrade, triage, or backlog pass has produced a list someone must rule on; or when a per-item conversation is burning round-trips.
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.3.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Decision Packet

**Version 1.1.0** (2026-08-29)

An agent that has analysed N items needs N decisions from its principal. Every default shape
fails at scale, and the measurement that produced this skill is blunt: **26 rounds of per-item
conversation produced 0 of 30 decisions. One packet produced 30 of 30, in one pass, in one
paste.**

| Shape | Why it fails |
|---|---|
| One question per turn | N round-trips. This is what cost 26 rounds. |
| One long prose report | The principal holds thirty judgments in their head, keeps their place, and composes a reply that re-identifies each item. |
| A table in chat | Readable, not operable. Nowhere to record a decision, no state if they stop halfway. |
| A form that submits somewhere | Needs a backend, and the reply still has to get back to the agent. |

The failure is not that the principal lacks information. **The medium collects no structure**, so
the burden of structuring the response falls on the person, every time, for every item.

**The property to preserve above all others: the principal's cost scales with the number of
*sittings*, not the number of *items*.**

## When to use it

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
  is not finished*. Do the analysis. The generator refuses a packet where no row carries a
  recommendation.

The failure mode of a good pattern is over-application. These three limits are the skill.

## The five load-bearing properties

Requirements, not suggestions. Each is why it worked.

1. **Self-contained rows.** Item, recommendation, reasoning, and a link to the underlying
   artifact. The principal never leaves the packet to decide.
2. **The recommendation is marked on the control, not merely stated in prose.** Agreeing costs one
   click. The agent's judgment does work instead of being described.
   **It is deliberately not pre-*selected*** — a packet that opens fully decided cannot distinguish
   "I agreed" from "I never looked", and would report decisions nobody made.
3. **A free-text box on every row, beside the buttons.** Never force a principal into your option
   set. In the origin run one such note, on one row, carried information no button could have.
4. **Local persistence keyed per item.** Thirty decisions is more than one sitting for anyone doing
   it properly. Storage access is guarded: where a browser blocks it the packet still works and
   says so in the summary.
5. **A paste-able summary the tool generates.** *This is the property that closes the loop.* The
   structure you need is produced by the packet, not composed by the person.

## Content requirements, which matter as much as the mechanics

- **Name filters from the content, not from generic severity.** "Needs a fix", "We disagreed",
  "Ready as written", "Not yet decided" — so the principal picks their own path through the set
  rather than going 1 to N.
- **Surface disagreement; never converge before the principal sees it.** Eight rows in the origin
  run showed two reviewers' conflicting verdicts and the principal broke all eight ties.
  Converging first would have shown a false consensus. Use the `disagreement` block.
- **A summary band before the detail**, so the shape of the work reads in three seconds.
- **Severity in form as well as words** — the coloured rail per row is how the eye finds exceptions
  while scrolling.
- **Recommend against your own prior work where that is true**, including failed hypotheses. A
  packet that only argues one way is a sales document, and the buttons stop being trusted.

## The reader contract (v1.1.0) — comprehension is a load-bearing property

The origin measurement has a dark twin, measured on the same principal on
2026-08-29: **a 15-row packet written in project-internal language collected
0 of 15 decisions.** Every mechanical property above worked — filters,
persistence, marked recommendations — and none of it mattered, because the
rows named things only the authoring session knew ("C1", "holdout",
"quarantine", "protected strata"). The principal's verdict: "written in some
alien or machine language." Structure without comprehension collects
nothing. The packets that ran 30/30 were about things the principal already
knew — articles, titles, links.

So a packet is a **stranger-read document**, and authoring one starts where
`synthesis-reader-briefing` starts: who reads this, what do they bring, what
does it ask, what do they leave with. Then, per row:

- **The label is plain language.** Internal IDs may appear as chips; they
  are never the name.
- **Context says what the thing IS** in words the reader already has,
  before any result about it.
- **An `impact` block states consequences, both ways** — what actually
  happens if they take the recommendation and if they don't, in outcomes
  the principal cares about (what ships, what it costs, what dies), never
  in internal treatment vocabulary. The generator renders it distinctly.
- **Options are labeled by consequence,** not by the agent's internal
  verbs. "Keep it out of your published skill; test once more" beats
  "retest".
- **Every surviving term of art gets a one-clause gloss** — inline on first
  use, or in the packet-level `glossary` band.
- **`audience` names the reader.** One sentence. If you cannot write it,
  you do not know who the packet is for, and neither will they.

`--strict-reader` makes the generator refuse a packet missing `audience` or
per-row `impact`. **Use it for every packet handed to a principal.** The
warnings print either way; strictness is the difference between a warning
you read and a packet they cannot.

## Use

```bash
python3 scripts/build_packet.py --schema              # the spec format
python3 scripts/build_packet.py spec.json -o packet.html --strict-reader
python3 scripts/build_packet.py spec.json --stdout    # to a pipe
```

Write a JSON spec, generate, hand over the file. It is self-contained: no build step, no
dependencies, no server. It opens from disk, over a local HTTP server, or published as an
artifact, in light or dark, on a phone or a laptop.

**Generate from a data array; never hand-author rows.** Thirty hand-written blocks drift. One
array with a render loop cannot. That is the whole reason this is a generator rather than a
template.

The generator validates before it emits and refuses to build a broken packet: duplicate ids
(they key persistence), a recommendation outside its own option set, a packet with no
recommendations at all, malformed disagreement blocks.

## Two defects that are permanent fixtures

Both shipped in the reference implementation; one reached the principal in real use. They are
regression-tested in `scripts/test_build_packet.py`.

- **Charset in the first bytes.** Without `<meta charset="utf-8">` ahead of everything, typographic
  punctuation renders as mojibake when served over a plain local HTTP server. *Found by loading
  the page, not by reading the source* — which is why the fixture asserts on bytes and why you
  should always open a generated packet before handing it over.
- **The copy control must never fail silently.** `navigator.clipboard.writeText` is blocked inside
  a sandboxed artifact iframe with no `clipboard-write` permission; in the origin run the button
  did nothing and *said* nothing, and the principal worked around it by hand. The required order:
  **select the textarea first** so a manual ⌘C/Ctrl+C always works, say something *synchronously*,
  then `document.execCommand("copy")` (which does work in sandboxed iframes), then the async API,
  and report honestly which path succeeded. A third fixture was added on 2026-08-28 after driving
  the real button surfaced an empty status line while the async promise was unsettled — an
  unbounded silent interval is the same defect as a permanent one.

## Relationship to other skills

- **`synthesis-autopilot`** should *call* this, not reimplement it. Autopilot requires "batched
  questions for the user"; this is the concrete artifact that requirement was missing. A
  round-trip budget only means something if one round-trip can carry many decisions.
- **The adversarial review family** — this is where an engagement surfaces its unresolved
  disagreements. Pair it with a status for findings that are not open, not conceded, and not the
  agents' to close.
- **The handoff queue** (`synthesis-project-management/scripts/handoff.py`) moves work *between
  agents*. The decision packet moves decisions *between agent and principal*. Together they are
  the two directions that stop routing everything through a person as the transport layer.

## Related

- `references/worked-example.md` — a complete spec and what it produces.
- `synthesis-reader-briefing` — the four questions every packet is authored
  against; the reader contract above is that skill applied to this medium.
- `synthesis-thinking-framework` — for deciding *what* to recommend before you build the packet.
- `synthesis-anti-shortcuts` — a packet whose rows hedge instead of recommending is the
  asking-as-shortcut costume in a new medium.
