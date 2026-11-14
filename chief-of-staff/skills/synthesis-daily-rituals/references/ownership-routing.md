# Ownership vs visibility (§3)

Read at the catch-up read (Day-Start Step 4), when an intake item needs an owner.

A task, follow-up, or email needing a reply belongs to exactly one
workspace and appears in that seat's records and nowhere else — recorded
twice, it gets worked twice or "handled" by nobody. A calendar
commitment is the opposite: owned by the creating workspace but visible
to every seat, read-only. Time cannot be separated even when tasks can.
Read each calendar through its own account's connector; a window no seat
has read is an unanswered question, not a free window.

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

## Conflict reports route to the movable side

When a seat finds two commitments that collide (reading each owned calendar
through its own connector, the account-routing guard choosing the account),
the seat applies Rule 3 and names the movable side. When one seat sees both sides it resolves inline; across
seats it messages the owning seat on the coordination bus. Movability is
a judgment call recorded in the report — `movable: <side> because
<reason>` — never a silent default. A report that cannot determine
movability goes to the principal as a candidate, and the principal is
loudly informed of every machine-made movability decision with the
opportunity to reverse it: the seat uses its full intelligence and
context toward the principal's best interests, and asks whenever doubt
exceeds the very small.

The coordination bus is the board: `synthesis msg <session id | project:<id>> "<text>"`.
