# Decision packet: writing the spec

Everything that decides whether a packet collects decisions: the six load-bearing properties, the material and prior positions each row must carry, the content requirements, and the reader contract. Moved verbatim from the 1.8.0 SKILL.md; only link paths changed. Read it before writing any spec.

Contents:
- The six load-bearing properties (binding rules 1 to 6 in full)
- Inspect the actual material: `review_assets`, `revision` and `delivery`
- Prior positions and contrary evidence: the `prior_position` block
- Content requirements: filters, disagreement, summary band, severity rail, recommending against your own work
- The reader contract (v1.1.0): plain labels, `impact` both ways, options labeled by what they do, consequences on the buttons, glosses, `audience`, `--strict-reader`

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
4. **Local persistence keyed by exact spec and item.** Thirty decisions is more than one sitting for anyone doing
   it properly. Storage access is guarded: where a browser blocks it the packet still works and
   says so in the summary. A change anywhere in the canonical spec starts fresh choices;
   an old click cannot silently acquire a new meaning.
5. **A paste-able summary the tool generates.** *This is the property that closes the loop.* The
   structure you need is produced by the packet, not composed by the person.
6. **Filed in the owning project, never only as a chat artifact.** The spec, the generated page,
   and the rulings the principal pastes back live in the owning synthesis project's
   `resources/artifacts/` as `<date>-<slug>-spec.json`, `<date>-<slug>.html`, and
   `<date>-<slug>-rulings.json`. Later versions receive a digest suffix; earlier
   bytes are preserved. A packet that exists only as a published Claude artifact is
   readable by one client in one conversation; the project directory is readable by every agent
   working the project, ChatGPT Codex included, and by the next session after this one is gone.
   `build_packet.py --file-into` files the first two; `record_rulings.py` files the third.

## Inspect the actual material

For decisions about correspondence, code, images, media or documents, include
structured `review_assets` plus the exact row `revision` and `delivery` envelope.
Read [the review-asset contract](review-assets.md) before constructing
these fields. It defines the closed data types, integrity checks, safe Markdown,
byte limits, copy/download behavior and unavailable-material refusal. Put the
complete artifact there; keep context and recommendations in their own fields.

The page renders material before the recommendation. The existing canonical
spec binds every content and delivery field to saved choices and returned
rulings. External references are never fetched automatically. Unavailable
material stays visible but cannot acquire a selected ruling. A byte-perfect
record still grants no authority and does not supersede an existing valid grant.

## Prior positions and contrary evidence

Before recommending a change, read the principal's exact prior statements in the
current task and selected durable record. A selected button never replaces an
accompanying note. If an earlier position applies, each row must include
`prior_position` with `statement` (exact words), `source_ref` (the actual evidence
location), and `evidence_for` / `evidence_against` lists. Each evidence entry has
`statement` and `source_ref`. Preserve original whitespace and wording; label an
inference in the evidence statement instead of attributing it to the principal.
An empty list means no evidence was recorded in this packet, not that none exists.

The packet displays this block before context and recommendations and includes it
in the spec-bound recorded ruling. A recommendation may disagree with the prior
position when the evidence supports doing so; show the conflict. No prior
position preselects a button or grants fresh execution authority. The new choice,
free-text note and exact prior evidence remain separately recoverable. If the
source is unavailable, report that missing input instead of inventing a position.

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
