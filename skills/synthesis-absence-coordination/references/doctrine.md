# Absence coordination: doctrine

Why an absence is a handoff, and the rules for who hears what, in what order, with what content. Read before drafting any notice, choosing tiers or types, or adapting the skill.

Contents:
- An absence is a handoff, not an announcement
- Notification order, and the hard gates
- Required content: coverage and reachability
- Recipient tiers: disclosure per tier; never use a distribution alias
- The personal-continuity tier
- Absence types: two triggers; the quiet type
- Release notes

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

## Release notes

**Version 1.0.0** (2026-08-12)

**Version 2.0.0** (2026-10-05) restructures the skill into the v5 format: binding rules
and contents first in SKILL.md, the rest moved verbatim into references/. No rule changed;
references/coverage-map.md maps every section.
