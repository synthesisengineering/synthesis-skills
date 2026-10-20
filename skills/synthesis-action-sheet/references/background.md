# Action sheet: background

Where the skill came from, why it is its own skill rather than a kind of decision packet, what
it shares with the packet, the skills around it, and its changelog. Read it when choosing between
this skill and a neighbor.

Contents:
- The origin
- Why a separate skill
- What it shares with the decision packet
- Related skills
- Changelog

## The origin

On 2026-10-19 a decision packet collected 31 of 31 rulings from its principal in one sitting.
The packet worked. What failed was everything after it: one chat reply mixed the items already
done, 13 staged sends awaiting approval codes, 4 new texts to check and 5 texts the principal had
to paste by hand into WhatsApp and LinkedIn. In the principal's words: "I am not able to clearly
and easily tell what you have already done, what I need to do, what I need to approve, what I
need to type, and what I need to send." They asked for a page like the packet: what they must
do, a copy button for each message and, better, a button that opens the conversation with the
text ready, a way to mark things done, and a way to tell the agent what happened. They use it
daily.

## Why a separate skill

A decision closes when it is made. An action closes when it is done, often later; it can be put
off and carried forward, and its completion needs confirming from a source. Packet rows require
a recommendation and consequences both ways, which actions do not have, and loosening those rules
would risk the property that produced the packet's results. The packet's own rule also holds:
unlike shapes on one page make a form, and a form is worse than a conversation. So the packet
stays the page for decisions, and the sheet is the page for what follows them.

## What it shares with the decision packet

The sheet reuses the packet's engine instead of copying it: `build_sheet.py` imports strict spec
reading (`strict_json`), the canonical spec bytes and digest, `write_preserved`, `slugify`,
`parse_iso_date` and the packet's filing (`file_packet`) from
`../synthesis-decision-packet/scripts/build_packet.py`, and `record_actions.py` imports the
packet recorder's paste transport (line splitting, note normalization, the JavaScript length of
the title). The frontmatter declares the dependency. The template copies the packet's look: its
color tokens, light and dark themes, copy order with its manual fallback, persistence keyed to
the exact spec digest, the paste-back summary with its binding line and the storage-blocked
trailer, and the integrity marker in the same form. What differs is the sections, the rows'
controls (marks, Me or Agent, Copy, Open), the links the generator builds, and a confirmation for
clearing that lives on the page, because the claude.ai viewer answers `confirm()` with false.

## Related skills

- `synthesis-decision-packet`: collect the rulings first; this sheet carries out what they leave
  to the principal. Its recorded rulings are a feed ([authoring.md](authoring.md)).
- `synthesis-message-guard`: the guard that stages sends behind approval codes. The Approve
  section shows those sends; the codes stay in chat.
- `synthesis-local-messaging`: reads Messages and WhatsApp databases for an authorized window
  (how marks on those channels are confirmed) and sends one approved iMessage.
- `synthesis-daily-rituals`: the daily plan whose items only the principal can do become rows,
  and whose "On your behalf" receives what was confirmed.
- `synthesis-agent-correspondence`: whose words and whose hands, for every message on the sheet.
- `synthesis-grounding-discipline`: record only what a source surfaced; a mark is a claim until
  then.

## Changelog

- **1.0.0 (2026-10-20)**: first release. The generator with built WhatsApp, Messages, LinkedIn,
  mail, phone and web links; refusal of approval codes, bad links, missing exact text, numbers
  not in E.164 and duplicate ids; Done for you, Approve and Do sections; Me or Agent on rows an
  agent may do; the recorder bound to the exact spec, with what the principal permitted on rows
  handed to the agent; carry-forward by exact id with `--agent-done` and `--not-found`; tests on
  the bytes and in a real browser.
