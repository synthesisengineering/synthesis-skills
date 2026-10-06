# Decision packet: background

The origin measurement, how this skill relates to its neighbors, the changelog and related skills. Moved verbatim from the 1.8.0 SKILL.md.

Contents:
- The origin measurement: why the other shapes fail
- Relationship to other skills: autopilot, the adversarial review family, the handoff queue
- Changelog 1.0.0 to 1.5.0
- Related

The 1.8.0 SKILL.md still carried this version line under its title, though its frontmatter said 1.8.0:

**Version 1.7.0** (2026-09-26)

## The origin measurement

When N unresolved decisions belong to the principal, collecting them one at a time
scales poorly. The measurement that produced this skill is blunt: **26 rounds of per-item
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

## Relationship to other skills

- **`synthesis-autopilot`** should *call* this for actual principal-owned gates, not
  reimplement it or return delegated decisions to the user. A
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
