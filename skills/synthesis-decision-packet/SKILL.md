---
name: synthesis-decision-packet
description: Collect many parallel decisions from a principal in one sitting instead of one per turn. Generates a self-contained HTML packet — one row per decision carrying the item, the agent's recommendation, the reasoning, and a link — with buttons labeled by what pressing them does, the consequence under each button, a per-row note box, local persistence, and a paste-able summary the principal returns in a single message; files the spec, the page, and the returned rulings in the owning project's resources/artifacts/ so every agent on the project can read them. Use when you owe five or more decisions of the same shape; when a review, migration, upgrade, triage, or backlog pass has produced a list someone must rule on; or when a per-item conversation is burning round-trips.
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.5.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Decision Packet

**Version 1.5.0** (2026-09-20)

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

## The six load-bearing properties

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
6. **Filed in the owning project, never only as a chat artifact.** The spec, the generated page,
   and the rulings the principal pastes back live in the owning synthesis project's
   `resources/artifacts/` as `<date>-<slug>-spec.json`, `<date>-<slug>.html`, and
   `<date>-<slug>-rulings.json`. A packet that exists only as a published Claude artifact is
   readable by one client in one conversation; the project directory is readable by every agent
   working the project, ChatGPT Codex included, and by the next session after this one is gone.
   `build_packet.py --file-into` files the first two; `record_rulings.py` files the third.

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
- **Options are labeled by what pressing them does,** never by a bare
  acknowledgement. Measured on 2026-09-14: on a 9-row packet, three rows
  offering "Yes, do that" / "No" collected notes instead of decisions — the
  principal could not tell what each button would do to the thing in
  question, so the note boxes carried what the buttons should have. "Keep
  them on my phone" / "Take them off my phone" is the accepted form. The generator raises a
  READER finding for a bare label (yes, no, ok, okay, cancel, accept,
  decline, approve, reject, do it, go, stop, and their "Yes, do that" /
  "No thanks" forms, compared after trimming punctuation and case, and any
  of these padded with a stopword: "Accept it", "Approve this", "Do that")
  and for two labels in one option set that do not differ in a content word;
  `--strict-reader` refuses to build, naming the row, the labels, and the
  accepted form.
- **The consequence sits on the button.** Each option button carries, under
  its label, what pressing it does: the option's own `consequence` when the
  spec gives one, otherwise `impact.accept` under the recommended option and
  `impact.decline` under every other one. The row's impact block stays as
  the row's summary; the text on the button is what the principal reads at
  the moment of choosing.
- **Every surviving term of art gets a one-clause gloss** — inline on first
  use, or in the packet-level `glossary` band.
- **`audience` names the reader.** One sentence. If you cannot write it,
  you do not know who the packet is for, and neither will they.

`--strict-reader` makes the generator refuse a packet missing `audience` or
per-row `impact`, or carrying option labels that name no consequence. **Use it
for every packet handed to a principal.** The warnings print either way;
strictness is the difference between a warning you read and a packet they
cannot.

## Use

```bash
python3 scripts/build_packet.py --schema              # the spec format
python3 scripts/build_packet.py spec.json -o packet.html --strict-reader
python3 scripts/build_packet.py spec.json --stdout    # to a pipe
python3 scripts/build_packet.py spec.json --strict-reader \
    --file-into PROJECT/resources/artifacts/         # + <date>-<slug>-spec.json, <date>-<slug>.html
python3 scripts/record_rulings.py paste.txt \
    --file-into PROJECT/resources/artifacts/         # -> <date>-<slug>-rulings.json
```

Write a JSON spec, generate, file, hand over the file. It is self-contained: no build step, no
dependencies, no server. It opens from disk, over a local HTTP server, or published as an
artifact, in light or dark, on a phone or a laptop.

**File it, then hand it over.** `--file-into DIR` writes a dated copy of the spec and of the page
into DIR after a successful build. DIR is the owning project's `resources/artifacts/` and must
already exist: the generator refuses a missing directory rather than creating one where you did
not mean. `--date YYYY-MM-DD` sets the date in the names (default: today). Publish the page as
an artifact too if that is how the principal will open it; the filed copy is the one other
agents read.

**Record what came back.** When the principal pastes the summary, save the paste to a file and
run `record_rulings.py paste.txt --file-into DIR`. It parses the exact text the packet's "Copy
summary" button emits and writes `<date>-<slug>-rulings.json` beside the spec and page: `packet`,
`ruled_on`, `decided`, `total`, and one ruling per row with `id`, `label`, `choice_label`,
`took_recommendation` (true, false for an override, null when undecided or when the row carried
no recommendation), `accepted_in_bulk` (the packet keeps bulk acceptance distinct from a
considered click, and so does the file), `recommended_label`, and `note`. It refuses text that
is not in that format, naming the line that failed, the form expected there and the text it
received; it reads a whitespace-only line as blank, since chat surfaces pad empty lines; it
refuses a paste whose row count or decided count disagrees with its own `Decided n of m.` line;
and it keeps an existing rulings file for the same date and packet unless `--replace` is passed.
Commit all three files with the project.

## Enforcement (v1.5.0) — generator output is verified, not trusted

Prose above tells the agent to generate; this section is what happens when
one freelances instead. Every page `build_packet.py` emits carries a
provenance marker pinning its embedded spec (`synthesis-decision-packet
spec-sha256`). `record_rulings.py` refuses a paste whose packet has no
filed `-spec.json`. And the context doctor's `skill-outputs` check fails
any packet page under a project's `resources/artifacts/` that is not
verifiable generator output: unmarked with no filed rulings is a defect
(rebuild with the generator or remove it); a marker that disagrees with
the embedded spec is a defect (never hand-edit generator output); a
closed record (unmarked but ruled) warns. The rule ships on every
machine with install, upgrade, and doctor — it is not a local note.

**Generate from a data array; never hand-author rows.** Thirty hand-written blocks drift. One
array with a render loop cannot. That is the whole reason this is a generator rather than a
template.

The generator validates before it emits and refuses to build a broken packet: duplicate ids
(they key persistence), ids with leading, trailing or doubled whitespace or a line break (the
summary line is `id  label`, split on its first double space), a line break in the title, a row
label or an option label (the paste is one line per field, and a packet that builds must file),
an option set with fewer than two options (a one-button set records no decision), two options
in one set sharing a value or a value that is not a non-empty string (the value keys the pressed
state and the summary label through a DOM dataset, which stores strings), a recommendation
outside its own option set, a packet with no recommendations at all, malformed option sets at
the packet level or on a row, malformed disagreement, impact, or glossary blocks.

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

## Changelog

- **1.5.0 (2026-09-20)** — Enforcement: the generator emits a provenance marker pinning the embedded spec; `record_rulings.py` refuses pastes with no filed `-spec.json`; the context doctor's `skill-outputs` check fails unmarked live packets as defects. After a session hand-authored two packets.
- **1.4.0 (2026-09-14)** — Option labels must name consequences: READER findings for bare
  acknowledgements and for two labels that do not differ in a content word, fatal under
  `--strict-reader`, with the row, the labels, and the accepted form in the message. Each option
  button carries its consequence under the label (`consequence` per option, else the row's
  `impact` mapped onto the buttons). Sixth load-bearing property: packets and rulings are filed
  in the owning project's `resources/artifacts/` — `--file-into`, `--date`, and the new
  `record_rulings.py`, whose parser is pinned to the summary format the page emits. Per-row
  option sets are validated like the packet-level set; ids with edge or doubled whitespace are
  refused. The worked example's options now name outcomes. Repair round the same day: a line
  break in the title, a row label, an option label or an id is refused, so a packet that builds
  can always be filed; a one-button option set, two options sharing a value, and a non-string
  value are refused; an acknowledgement padded with a stopword ("Accept it", "Do that") is
  caught; `record_rulings.py` counts the title underline in UTF-16 units as the page does,
  reads whitespace-only lines as blank, and every refusal quotes the text it received; the
  worked example's paste and rulings file match its two-row spec, and a fixture holds them to
  the parser.
- **1.3.0 (2026-08-29)** — Ids must be non-empty strings: JSON `1` and `"1"` become the same
  localStorage key, so JSON-distinct ids could share saved state.
- **1.2.0 (2026-08-29)** — The relationship section names the handoff queue as the
  agent-to-agent transport.
- **1.1.0 (2026-08-29)** — The reader contract: `audience`, `glossary`, per-row `impact`, and
  `--strict-reader`, after a 15-row packet in project-internal language collected 0 of 15.
- **1.0.0 (2026-08-28)** — First release: the packet, the five properties, and the two
  permanent fixtures.

## Related

- `references/worked-example.md` — a complete spec, the filed copies, the paste that comes
  back, and the rulings file it becomes.
- `synthesis-reader-briefing` — the four questions every packet is authored
  against; the reader contract above is that skill applied to this medium.
- `synthesis-thinking-framework` — for deciding *what* to recommend before you build the packet.
- `synthesis-anti-shortcuts` — a packet whose rows hedge instead of recommending is the
  asking-as-shortcut costume in a new medium.
