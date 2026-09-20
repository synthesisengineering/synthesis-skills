# Ownership vs visibility (§3)

A task, follow-up, or email needing a reply belongs to exactly one
workspace and appears in that seat's records and nowhere else — recorded
twice, it gets worked twice or "handled" by nobody. A calendar
commitment is the opposite: owned by the creating workspace but visible
to every seat, read-only, through the shared time-block layer. Time
cannot be separated even when tasks can.

## Routing rules (apply in order, at intake)

1. **Rule 1 — account arrival → the manifest owner.** The workspace
   whose `.agents/mailboxes.yaml` declares the account owns whatever
   arrives there. Mechanical — look it up, do not judge it.
2. **Rule 2 — no account → the deletion-unit test.** Ask which
   workspace's records the item must survive in: obligations that
   outlive a job route to the personal workspace. Judgment — record the
   reasoning with the item.
3. **Rule 3 — a work/personal time collision → the movable-item seat.** The seat
   holding the item that can move owns the conflict. Judgment — see the
   conflict report shape below.

**Fail-closed:** when no rule fires, the item becomes a CANDIDATE
presented to the principal in the same turn — never double-recorded and
never dropped. Every owned item carries `owner:` (workspace) and
`owner_rule:` (`1`, `2`, `3`, or `candidate-confirmed`) so a later seat
sees why it landed where it did.

## The shared time-block layer

One JSON file, synced across the principal's machines through the
personal repo — never per-machine local state, or seats strand:

```
<personal-repo>/coordination/time-blocks.json
```

Schema (`synthesis-time-blocks/v1`): an object with the `format` tag and
a `blocks` list. Each block carries `owner`, real-title `title`,
ISO-8601 `start`/`end` with a UTC offset, and `source` calendar, plus
optional `published_by` seat and `published_at` moment. Labels carry
real titles — every seat is the principal's own trusted team, and full
detail makes better conflict calls than opaque Busy markers. The repo is
private to the principal; nothing here is publishable elsewhere.

## Seat publish procedure (every ritual sweep)

1. Read this seat's owned calendars for the look-ahead window through
   the seat's own calendar access (MCP tools a script cannot call —
   publishing is a seat duty, not a script).
2. Rewrite each owned commitment as one block: owner workspace,
   start/end, real title, source calendar.
3. Hand-enter blocks for accounts beyond the agent's reach (by hand
   means by the AI system, from whatever the principal can see — never
   ask the principal to type calendar data) so the layer covers what no
   single seat's calendar check can.
4. Replace only this seat's own blocks in the shared file; other seats'
   blocks are theirs to publish. Then `overlap.py validate --layer` the
   file — a seat that cannot validate does not publish.
5. This procedure never writes to a calendar. Shared reads come first;
   agent writes to calendars are a later design, not this one.

## The overlap call (any seat, any window)

```bash
python3 <synthesis-chief-of-staff-root>/scripts/overlap.py overlaps \
    --layer <personal-repo>/coordination/time-blocks.json \
    --from <ISO-8601> --to <ISO-8601> [--json]
```

`--layer` may be omitted when `$SYNTHESIS_TIME_BLOCKS` points at the
file. The script takes a window and returns overlaps across owners —
same-owner pairs are excluded, touching endpoints are not overlaps —
with no MCP calls and no writes, so it runs identically in tests and in
rituals. Fixture layers live beside the script in
`synthesis-chief-of-staff/scripts/fixtures/`.

## Conflict reports route to the movable side

The script reports pairs; the calling seat applies Rule 3 and names the
movable side. When one seat sees both sides it resolves inline; across
seats it messages the owning seat on the coordination bus. Movability is
a judgment call recorded in the report — `movable: <side> because
<reason>` — never a silent default. A report that cannot determine
movability goes to the principal as a candidate, and the principal is
loudly informed of every machine-made movability decision with the
opportunity to reverse it: the seat uses its full intelligence and
context toward the principal's best interests, and asks whenever doubt
exceeds the very small.

## Coverage reporting

The layer report names its denominator like every other sweep: how many
owner workspaces published fresh blocks for the window, which seats are
stale or missing, and which accounts entered by hand. "No overlaps"
without that denominator is not a result — it may mean no seat
published.
