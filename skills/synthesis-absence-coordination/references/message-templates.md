# Message templates, per tier

Draft skeletons for each recipient tier. These set the *shape and tone*; the agent fills
them from config and the absence record, and the sender's own voice skill (if one exists)
governs the final wording. Placeholders in `<angle brackets>`.

Two rules apply to every template:

1. **The content policy is a ceiling, not a suggestion.** A `dates_only` tier's message
   contains dates and nothing else — no city, no reason, no color. If a sentence feels
   informative, check the policy before keeping it.
2. **Every work-tier message answers the three questions** — who decides, what waits,
   how to reach — or it is not ready to send.

---

## `principals` — one email, assistants cc'd

The highest-stakes message in the system, and the one the agent drafts but never sends.
Because the assistants read the same text, it must work for both audiences: personal
enough to be from the sender, complete enough that an assistant can act without a
follow-up.

> **To:** `<manager>`, `<ceo>` · **Cc:** `<manager's assistant>`, `<ceo's assistant>`
> **Subject:** Out of office <start>–<end> — coverage in place
>
> <Manager first name>, <CEO first name> —
>
> I'll be out <start date> through <end date> (<city, if policy allows — one clause,
> e.g. "at a leadership summit in Dubai">), back <return date>.
>
> Coverage while I'm out:
> - **<Decision class 1>** — <name> decides.
> - **<Decision class 2>** — <name> decides.
> - Anything else keeps until I'm back; I've told the team the same.
>
> I'll be <reachability: e.g. "checking email once each morning — <assistant name> can
> reach me by phone if something truly can't wait">.
>
> Cc'ing <assistant names> so this is on the calendars early. I'll flag anything that
> shifts.
>
> <sign-off>

Why this shape: the coverage list is scannable by an assistant in five seconds; the
reachability line prevents both over-escalation and sat-on urgencies; the cc is named in
the body so nobody wonders why they received it.

## `direct_reports`

> **Subject:** I'm out <start>–<end> — who decides what
>
> Team —
>
> I'm out <start> through <end>, back <return date>.
>
> While I'm gone:
> - **<Decision class>** — go to <name>. Their call is my call.
> - **<Decision class>** — go to <name>.
> - **Everything that can wait: let it wait.** Genuinely. A queue for my return beats a
>   guess in my absence — except where waiting causes real harm, and then:
> - **Urgent path:** <escalation: e.g. "message <name>, who knows how to reach me">.
>
> <sign-off>

The explicit permission to defer is the most useful sentence in the message. Do not cut it.

## `team_group` — chat post, gated behind principals

Short. A group post is a broadcast, not a briefing — link or point to detail rather than
inlining it.

> OOO <start>–<end> (back <return date>). <Name> covers <area>, <name> covers <area>;
> everything else holds until I'm back. Urgent-only path: <route>. 🌴

## `family` — `dates_only`

Individually addressed or one email to the explicit list — never an alias.

> **Subject:** Away <start>–<end>
>
> Hi all — a heads-up that I'll be traveling <start date> to <end date>. Back <return
> date> and reachable as usual on <channel>. More when I see you!

Note what is absent: destination, purpose, employer. `dates_only` means only this.

## `co_parenting` — `dates_child_logistics`

Different audience, different facts: this one is about the child's schedule, not the
absence.

> **Subject:** <Child>'s schedule, <date range>
>
> <Names> —
>
> Travel note from my side: I'm away <start>–<end>. For <child>:
> - <Pickup/dropoff/custody logistics affected, with dates and places>
> - <What stays unchanged>
> - <Fallback if plans shift, and by when you'll confirm>
>
> Call/text as usual if anything needs adjusting.

## `personal_continuity` — `dates_timezone_facilities`

The trainer/therapist/tutor tier. Time zone is the headline; facilities research is
attributed and dated.

> **Subject:** Travel <start>–<end> — <tz offset> from you, gym details inside
>
> <Name> —
>
> I'm traveling <start> to <end>. The key fact: I'll be on <time zone> — **<N> hours
> <ahead of/behind> you**, so my usual <time> slot lands at <their-local time> your time.
>
> Proposed slots (all times yours):
> - <Day 1>: <slot> — <note if unusual>
> - <Day 2>: <slot>
> - <…one line per day for daily cadences>
>
> I'm staying at **<hotel>, <address>**. Their fitness center, per <source, e.g. "the
> hotel's site"> as of <date checked>: <hours>; <equipment summary>; <photos link if
> found>. <Any gap: "No free-weight details listed — worth assuming machines only.">
>
> Flag any day that doesn't work and I'll re-cut the plan.

## `external_counterparts` — `dates_only`, no purpose

> **Subject:** Out of office <start>–<end>
>
> A quick note that I'll be out of the office <start> through <end>. For anything on
> <shared matter> in that window, <name> (<address>) has context. Otherwise I'll pick
> things up on my return.

## `quiet` type — minimal visibility

Smallest possible set, smallest possible message. No reason given; none owed.

> **Subject:** Out <dates>
>
> I'm out <start>–<end> and largely offline. <Name> covers anything urgent. Thanks for
> keeping this between us until I'm back.

## Out-of-office auto-responder

Same three answers, addressed to strangers. Set on departure; **cleared on return** —
the clear is part of the template's contract.

> I'm out of the office until <return date>, with limited access to email.
>
> - For <area>: contact <name> (<address>).
> - For urgent matters: <route>.
> - Everything else: I'll reply after <return date>.
