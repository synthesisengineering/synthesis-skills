# Chief of staff: preserved text

Text replaced on 2026-10-05 when `scripts/overlap.py` was retired (v5 code
verdict: REPLACE, "the layer was never published here; day-start reads each
account's calendar through its connector") and the onboarding interview it
named stopped existing. Verbatim; the replacement sits at the same place.

## SKILL.md, Scheduling protocol, step 1 (1.3.0)

1. **Read the principal's calendar FIRST.** No scheduling sentence is written
   before the actual calendar for the window is fetched. An agent with
   calendar access that asks the counterpart for their availability has the
   relationship backwards. Since v1.3.0 the check consumes the shared
   time-block layer (`coordination/time-blocks.json` in the personal repo,
   via `scripts/overlap.py overlaps` for the window) instead of only the
   seat's own reachable accounts: the layer carries every seat's owned
   blocks with real titles, including hand-entered blocks for accounts
   beyond the agent's reach. A window the layer does not cover is an
   unanswered question, not a free window — name the missing seat before
   proposing anything inside it.

## SKILL.md, binding rules 4 and 6 (2.0.0 before the script change)

4. **Read the calendar and the shared time-block layer before writing any scheduling sentence.** A window the layer does not cover is an unanswered question, not a free window.
6. **Release or move only holds the agent created, matched by id.** Ask `holds_state.py is-releasable`; never hand-edit the ledger or judge releasability from memory.

## SKILL.md, Configuration contract (1.3.0)

Create the file by running `synthesis-onboarding init`, or copy
`preferences.example.json` and replace its synthetic defaults. The shipped
example contains no people, organizations, or account details.

## references/background.md, Related (1.3.0)

- The message-guard skill enforces grounding on anything this skill drafts.

In v5 the message-guard skill is the send guard: approval of the exact call and a register scan; the grounding ledger it once checked is gone.

## What `overlap.py` was, from its docstring

Ownership is exclusive — a task belongs to exactly one workspace — but
visibility is shared: every seat publishes its owned commitments' time
blocks, with real titles, to one JSON layer file in the personal repo
(`coordination/time-blocks.json`), and any seat can call this script to
find conflicts across owners for a window.

Layer resolution: `--layer PATH`, else `$SYNTHESIS_TIME_BLOCKS`. There is
no default path — the personal repo lives somewhere different per machine,
and a wrong guess would silently read a stale copy.

The rule that survives: a window nobody has read is not a free window. It is
now step 1 of the Scheduling protocol and binding rule 4, applied to each
account's calendar instead of a published layer.
