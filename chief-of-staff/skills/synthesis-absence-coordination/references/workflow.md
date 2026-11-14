# Absence coordination: workflow, ledger and rollout

The six workflow steps in full, the ledger, the rollout order and how to adapt the skill. Read when running an absence end to end, or when introducing the skill.

Contents:
- Workflow: 1 pre-flight, 2 calendar, 3 notify, 4 logistics, 5 out of office, 6 return
- The ledger
- Rolling it out: pilot on the tiers that forgive mistakes
- Adapting this skill

## Workflow

### 1. Pre-flight — before anyone is told

- **Sweep every calendar.** All accounts, and explicitly any calendar outside your
  mirroring layer. If some tool blocks time across your calendars, know its coverage
  gaps: a calendar on a different provider commonly sits outside the mirror, blocks
  nothing elsewhere, and is invisible precisely when you are checking for conflicts.
- **Enumerate recurring instances** inside the window — standups, 1:1s, councils — and
  produce a decline-or-delegate decision for each. They do not cancel themselves, and
  leaving yourself listed as an attendee means colleagues hold slots for someone who will
  not appear.
- **Resolve coverage and reachability.** Gate: no sends until both exist.
- **Resolve the destination time zone** if travelling. Needed by the continuity tier and
  by anyone proposing meetings across the window.

### 2. Calendar

Personal event; work out-of-office; family-visible calendar; any shared team or
leadership calendars in config. Work-calendar titles should be **discreet by default** —
colleagues can see them, and the detail belongs on the personal side. `OOO — personal` is
sufficient; a child's travel itinerary on a corporate calendar is not.

### 3. Notify

Tier order, gates enforced. Principals drafted for the human to send, assistants cc'd.
Group channels last.

### 4. Logistics (travel types)

- **Itinerary forwarding.** Forward booking confirmations to your travel-management
  service. **Send from the address verified on that account** — most services silently
  discard mail from unverified senders. There is no bounce, no trip, and no symptom until
  the trip is missing. Confirmations arrive wherever the booking was made, so a forward
  straight from a work account will vanish. Route through the verified address, then
  **verify the trip was actually created**.
- **Family and co-parenting notes**, per their content policies.
- **Personal-continuity note**, with time zone, lodging, and researched facilities.

### 5. Out of office

Set the auto-responder with the same coverage and reachability content. Schedule the
**clear**. A responder still firing after return is a small recurring embarrassment that
signals nobody owns the system.

### 6. Return

Hand off to `synthesis-catchup-ledger` for the window sweep: what moved, what was
decided, what is now owed. **An absence workflow that ends at departure is half a
workflow.** Clear the auto-responder, restore declined recurring meetings, and close the
ledger rows.

---

## The ledger

Every notification writes a row: tier, recipient, channel, content policy applied, drafted
/ sent / acknowledged, timestamp, and a stable `absence_id`.

The ledger is what makes the system **idempotent** and **auditable**. Re-running an
amended trip updates rows rather than reposting. "I told them" becomes checkable rather
than remembered. Where a `drafts/_LEDGER.md` convention already exists in the user's
workspace, write there rather than inventing a parallel mechanism.

---

## Rolling it out — pilot on the tiers that forgive mistakes

The tiers differ not only in content but in **cost of error**, and the rollout order
should follow that gradient, not the org chart:

1. **First cycle: `personal_continuity` and `family` only.** A misworded note to your
   trainer costs a shrug. These tiers also exercise the hardest machinery — time zones,
   facilities research, per-day proposals — so they are the *better* test, not just the
   safer one.
2. **Second cycle: work tiers as drafts.** Let the agent produce the principals and
   direct-report drafts for a real absence, and send them yourself. You are editing the
   system's voice while the stakes are a paste-and-tweak.
3. **Only then: promote tiers to `agent_send_after_approval`** — and the principals tier
   never promotes at all.

This ordering is doctrine, not caution for its own sake: trust in an EA — human or
agent — is built at the periphery and spent at the center. Earn it in that order.

## Adapting this skill

The tier names, gates, and types here reflect one shape of working life. The failure modes
in "The five failures" are the durable part. If your organization is flatter, collapse
`principals` and `direct_reports`. If you have no assistants, drop the cc rule — the
underlying principle (**the people most affected hear it first, and directly**) survives
the loss of the specific tier.

What should not be adapted away: coverage as required content, the group-post gate, the
quiet type, and the return step. Those are the four that people are most tempted to skip
and most regret skipping.
