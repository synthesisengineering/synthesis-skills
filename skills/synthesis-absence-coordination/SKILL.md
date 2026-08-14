---
name: synthesis-absence-coordination
description: Coordinate an absence end to end — vacation, conference travel, family visits, medical leave — the way a good chief of staff would. Covers the notification order that protects relationships (principals hear it from you, never from their own assistant or a group channel), coverage and reachability as required content rather than afterthoughts, recurring-meeting release, the personal-continuity tier that keeps a trainer or therapist or tutor in the loop while you travel, travel-logistics forwarding, out-of-office set AND clear, and the return sweep. All names, tiers, channels, and lead times load from a private config, so the skill is publishable and the configuration is yours. Use when planning time off, booking work travel, announcing an absence, arranging coverage, or returning from one.
license: "Apache-2.0"
depends_on: ["synthesis-chief-of-staff", "synthesis-agent-correspondence", "synthesis-catchup-ledger"]
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Absence Coordination

**Version 1.0.0** (2026-08-12)

## An absence is a handoff, not an announcement

Most "out of office" tooling answers one question: *is this person away?* That is the
least useful question anyone has.

The questions people actually have are: **who decides in their place, what can wait, and
can I reach them if it truly cannot.** An absence notice that omits those does not remove
a blocker — it relocates it, from your calendar into someone else's inbox, where it sits
until you get back and discover a week of stalled decisions.

This skill treats an absence as a **handoff with a scheduled reversal**. Every protocol
below follows from that.

It also treats an absence as a **relationship event**. Who hears first, who hears what,
and who never hears at all are not implementation details. They are the whole thing.

## Configuration contract

All specifics — names, addresses, tiers, channels, lead times, group IDs — live in a
private config the skill reads at load time:

```
~/.synthesis/absence-coordination/config.yaml
```

The skill is generic and publishable; the config is neither. Full schema:
[`references/config-schema.md`](references/config-schema.md). Starting point:
[`example-config.yaml`](example-config.yaml). Per-tier draft skeletons:
[`references/message-templates.md`](references/message-templates.md). Fifteen-minute
adoption path: [`references/quickstart.md`](references/quickstart.md). Validate with:

```bash
python3 validate_config.py ~/.synthesis/absence-coordination/config.yaml
```

**If the config is missing, STOP and say so.** Announcing an absence without knowing the
tier order is not a partial success; it is the specific failure this skill exists to
prevent. Never hardcode a name, address, or channel that belongs in config.

**Shared config.** Where `synthesis-chief-of-staff` is installed, this skill reads its
preferences file for calendar accounts, assistant relationships, and travel-disclosure
rules rather than duplicating them. One fact, one home. If both files define the same
fact, the chief-of-staff config wins and this skill's copy is a bug.

---

## The five failures this skill prevents

Everything below is machinery for these. When adapting the skill, keep the failures in
view; the machinery is negotiable, the failures are not.

1. **The relocated blocker** — an absence announced with no delegate.
2. **The secondhand notice** — someone's manager learns of their absence from a group
   channel, or from their own assistant, instead of from them.
3. **The silent conflict** — dates announced that collide with a commitment on a calendar
   nobody checked.
4. **The abandoned commitment** — recurring meetings left un-declined, a trainer left
   guessing, an auto-responder still firing a week after return.
5. **The default to disclosure** — a system that can only broadcast, so it goes unused
   exactly when discretion matters most.

---

## Notification order — the part that protects relationships

Order is the single highest-risk element of an absence, and the risk is invisible until
you get it wrong. Two failure modes pull in opposite directions:

- Tell the **assistants first** and your manager may hear about your absence from their
  own assistant. A small indignity, and entirely avoidable.
- Tell the **principals first and only**, then their assistants days later, and you have
  starved the people whose job is protecting those calendars of the lead time that makes
  them useful.

**The resolution is not a timing rule. It is one message.**

> **Write to the principals; cc their assistants.**

One email. The principals hear it from you directly. The assistants receive identical
lead time in the same instant. There is no ordering to enforce because there is no gap.
A whole class of sequencing bug is deleted rather than guarded against.

Configure this as `cc: tier:exec_assistants` on the principals tier. Because cc'd
assistants read the same text, the draft must work for both audiences at once: personal
enough to be from you, complete enough that an assistant can act without a follow-up.

### The hard gates

Enforced, not advisory. A gate that fails **blocks the step** — it does not warn and
continue.

| Gate | Why |
|---|---|
| **No group post before the principals are notified** | A manager learning of a report's absence from a team channel is a real, avoidable injury. Groups are last, always. |
| **No send before a conflict check across every calendar** | Including calendars outside any mirroring layer (see Pre-flight). Announcing colliding dates is worse than not announcing. |
| **No send before a coverage statement exists** | Coverage is required content, not a nice-to-have. If nobody covers, that is itself the statement — say so explicitly. |
| **Principal-tier messages are never agent-sent** | `send_mode: draft_only`. The agent drafts; the human sends. A note to your CEO about your own absence is not a message to automate. |
| **Amendments update existing rows, never repost** | Trips move. Re-running must amend. Double-posting to a group is how automation embarrasses its owner. |

---

## Required content: coverage and reachability

Every notice to a work tier carries both. A notice missing either is incomplete and the
skill should refuse to send it.

### Coverage

Per audience, in plain terms:

- **Who decides what.** Name a person per decision class, not one catch-all deputy.
  "Ana for anything on the knowledge base, Jason for CSA delivery, everything else waits"
  beats "Ana is covering."
- **What simply waits.** Explicitly. Permission to defer is the most useful thing you can
  give someone, and the thing they will not assume.
- **What must not wait**, and what to do with it.

**Coverage is sourced, not invented.** Set `coverage.source: external` and the skill
requires a coverage statement supplied by whoever owns the org context — for many people
that is a work-operations project or the manager themselves. This skill will not
improvise who covers your decisions. Getting that wrong is worse than saying nothing.

### Reachability

"Out of office" spans everything from *"I read email once each morning"* to *"genuinely
unreachable, satellite phone only."* Colleagues cannot calibrate without being told, so
they either over-escalate or sit on something urgent for a week. State:

- **Channel** — which one actually reaches you, and which are dead.
- **Frequency** — once a day, twice a week, not at all.
- **The escalation path** — what rises to "contact me anyway," and through whom.

---

## Recipient tiers

Tiers are defined in config; the skill supplies the ordering, the gates, and the content
rules. A tier is not just a mailing list — it is an audience with a **content policy**.

| Tier | Typical content | Notes |
|---|---|---|
| `principals` | dates, city, coverage, reachability | Draft only. Assistants cc'd here. |
| `exec_assistants` | as above | Normally reached as cc, not separately. |
| `direct_reports` | dates, coverage, reachability | A group post does not substitute for telling your reports. |
| `peers_stakeholders` | dates, coverage | Optional; scales with seniority. |
| `team_group` | dates, coverage pointer | Chat channels. **Gated behind principals.** |
| `family` | dates only | Explicit recipients — see "Never use an alias." |
| `co_parenting` | dates plus child logistics | Distinct from family: different facts, different tone. |
| `personal_continuity` | dates, **time zone**, lodging, facilities | See below. |
| `external_counterparts` | dates only, no purpose | Clients, vendors. Disclosure-minimal by default. |

### Disclosure is per tier, and it is mechanical

Business travel commonly warrants *dates and city*; purpose only where broadly
shareable. Personal absence commonly warrants *dates only*. Encode this as
`content:` on the tier so it is enforced rather than re-decided under time pressure —
the moment it becomes a judgment call made while rushing, it will eventually be made
wrong. When in doubt, the narrower content wins.

### Never use a distribution alias for a tier

Use explicit recipients in config. An alias seems tidier and is worse in four ways:

- **Opaque.** You cannot audit who was actually told.
- **Silently breakable.** Aliases die in provider migrations without a bounce; the first
  symptom is a family member who did not know you left the country.
- **Single-content.** One alias cannot serve two content policies, and family and
  co-parenting audiences need different facts.
- **Redundant.** The alias existed so a *human* had one address to remember. An agent
  reading a config does not need the shortcut.

---

## The personal-continuity tier

**The tier most absence systems do not have, and the reason this one is worth installing.**

Work coordination is the well-trodden half of an absence. The neglected half is that
travel disrupts **standing personal commitments** — a daily trainer, a weekly therapist,
a tutor, a music teacher, a caregiver, a standing call with a parent. These people need
more than "away." They need what they cannot look up.

Its content is unlike any other tier's:

- **Time zone, not city.** The operative fact for agreeing a daily slot is the offset. A
  trainer does not need to know you are in Dubai; they need to know you are UTC+4 and
  that 07:00 your time is 23:00 theirs.
- **Lodging and local facilities.** Hotel name and address, so a trainer can plan around
  the gym.
- **Facilities research, done for them.** With `research.lodging_facilities: true`, the
  agent looks up the hotel's fitness facilities — equipment, hours, pool, photos — and
  includes that in the note. Do not offload a lookup you can perform.
- **A per-day proposal, not a notice.** For daily commitments, propose a workable slot for
  each day of the trip against the destination time zone and the counterpart's own hours.

**Sourcing rule.** Facilities research must be attributed and dated — hotel gyms are
renovated, close, and change hours. Say where the information came from and when it was
retrieved. Never present a facility as confirmed on the strength of a marketing page;
"listed on the hotel's site as of 12 Aug" is honest, "has a Peloton" is not.

---

## Absence types

Config defines them; four cover most needs.

| Type | Lead time | On commit | Travel logistics |
|---|---|---|---|
| `vacation` | long | yes | yes |
| `conference` | long | yes | yes |
| `family_visit` | medium | no | no |
| `quiet` | none | no | no |

### Two triggers, not one

Lead time is a *deadline*, not a schedule. A trip booked four months out should not sit
unannounced for three of them.

- **`notify_on_commit`** — fires the moment the commitment is real, to a small cohort
  that benefits from maximum warning: typically the assistants who protect the calendars,
  and family. This is the trigger that prevents conflicts, because it lands before the
  conflicting things get scheduled.
- **`lead_time_days`** — the full announcement, on schedule.

Booking a conference in March for October means the assistants and your family hear in
March. Everyone else hears in September.

### The quiet type

Medical appointments, family emergencies, interviews, bereavement, anything personal.
`visibility: minimal` holds the calendar and notifies the smallest necessary set while
**suppressing** group posts and wide announcements.

This is not a nice-to-have. **A system that can only broadcast will be abandoned exactly
when discretion matters most** — and a tool you cannot use on your worst week is a tool
you do not trust. Ship the quiet path or people will route around the whole system.

For quiet absences, coverage still applies. Discretion about *why* is not discretion
about *who decides in your absence*.

---

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
