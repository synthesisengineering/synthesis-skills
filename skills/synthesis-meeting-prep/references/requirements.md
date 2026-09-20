# Meeting prep — requirements

Open-source requirements for `synthesis-meeting-prep`. This document is
the public, workspace-agnostic core. It generalizes hard-won experience
preparing a principal for executive 1:1s, peer conversations, large
forums, and external meetings: five consecutive rejected drafts of two
prep documents, each rejection naming a requirement the next draft
still failed. The through-line of every failure: **each draft was
written from what the agent had recently read rather than for the
person who would read it.**

## R1 — The document is about what to discuss

Things to avoid go in a short footer at the bottom, not distributed
through the body and not weighted as a theme. One glanceable list,
with a word of why where it is not obvious.

Corollary: do not warn about things the principal would never do. A
warning is only worth its line if the mistake is plausible.

## R2 — Audience model comes first and governs everything

Before drafting, state: who they are to the principal (peer / boss /
report / skip-level / external / mixed room), how technical they are,
and what they care about. Then write to that.

- Peer, non-technical → business outcomes. No ticket numbers, no
  infrastructure, no incident detail, no bundle sizes, no vendor
  product names where a plain phrase works.
- Peer executive → partnership, their people, what is coming that
  touches their org.
- Boss → judgement and decisions, not activity.
- Report → clarity, direction, growth; decisions they are waiting on.
- Skip-level → listening posture; their reality, not a broadcast.
- Engineering audience → the detail is the substance.
- External (customer, vendor, partner) → outcomes and relationship;
  nothing internal-only, nothing discoverable-risky.
- Mixed room → write to the least technical decision-maker present;
  detail goes in the if-asked section.

## R3 — Dense, not long

Cut words and cut padding. Never cut facts. Wordiness and substance
are independent axes; trading one for the other is the classic
over-correction (cut the salad, keep the facts).

Padding: explaining why an item is in the document · meta-commentary
about the document · restating a point after making it · the X-not-Y
construction · aphorisms · throat-clearing openers.

Substance: what shipped, what it does for the business, who did it,
what changed, what is decided, what is open, what to ask.

## R4 — Real accomplishments, named and translated

Recent delivery is mandatory content, sourced from the actual record —
commits, tickets, channel traffic, transcripts — and then **translated
into the reader's language.** Same fact, two registers: the business
outcome for an executive, the ticket number and bundle size only for
an engineering reader. Every accomplishment carries its provenance;
nothing is asserted that was not verified against the record.

## R5 — Strategic altitude alongside the tactical

The document must make the principal legible as a leader and a
thinker, not only as someone who ships: where the work is heading,
what the principal believes about it, what this person should
understand about the direction. Tactic-only prep makes the principal
look like a status reporter.

## R6 — Appreciation of others, specific and generous

Name people and say what they actually did. For peers, credit their
teams. Generic praise is worse than none. The goal with a peer is
that they leave feeling good about the partnership and quietly
impressed — achieved by substance and credit, never by self-promotion.

## R7 — Grounded and human in register

No dramatic or grandiose framing. No slogans. No invented precision —
no "every month," no "wildly," no counts that were not measured.
Plain, direct, numbered when there is more than one point, willing to
say "I think."

### R7b — Every sentence carries a fact or a position

Delete any sentence that announces what is coming instead of saying
it, restates what it just said, or exists to sound considered.

Named offenders:

- Announcing — "One thing that's changed and I think is
  underrated:" Say the thing.
- Self-restating in one sentence — the `X, not Y` shape is the
  single most reliable tell.
- Trailing flourish — sentences that re-assert confidence after the
  point is made.
- Filler assent — agreeable noises with no content.

### R7c — No name-dropping as an opener

Opening a large meeting with "X and I were talking" trades on a
private relationship in front of people who were not in it. Attribute
an idea when attribution is the point; otherwise state the idea. Fine
in a three-person room; wrong in a fifteen-person forum.

## R8 — Usable during the meeting, not just before it

Scannable. The principal should be able to look down mid-sentence and
find a line. Headings that say what is under them. Short bullets. The
one decision or ask must be findable in under five seconds.

## R9 — Positive framing on problems

Do not volunteer a defect nobody has asked about. Lead with what is
being built and where it is going; hold a prepared one-line answer
for the problem in case it comes up. Proactive disclosure is right
with the principal's own boss and wrong in a large forum, where it
trades a fixed problem for a remembered one. The line: disclose
upward and 1:1 by default; in forums, disclose only what the room
needs to decide.

## R10 — Prep states its own basis

Every pack names the sources it was built from (which transcripts,
threads, tickets, docs — and the newest source's date). A prep whose
basis is stale or thin says so up front. No basis, no trust.

## R11 — The debrief closes the loop

Prep without capture loses the loop. After the meeting: verify the
transcript (transcript-primary; never derive attribution-bearing
claims from a summary), extract decisions / commitments with owners
and dates, draft the follow-ups, and record the prep-vs-reality gap —
what the prep missed is the most valuable single input to the next
prep for the same people.

## R12 — Reader profiles compound

A small per-person file — relationship, technical depth, what they
care about, what they have already been told, what landed last time —
prevents entire classes of failure. The skill maintains these
profiles and consults them before drafting; the debrief updates them
after.

## Factor inventory

Prep varies along the factors below — see
[factor-inventory.md](factor-inventory.md) for the full catalog
(60+ factors across meeting, participants, principal, knowledge,
risk, and output). The skill weighs every factor and says which
ones drove the shape of the pack. No factor is one-size-fits-all:
a 15-minute standup gets five lines, a board review gets the full
pack, and the skill explains the sizing in one line.

## Structures to test

One shape with sections dropped, varying by meeting type —
see [structures.md](structures.md). Sections that do not apply get
dropped rather than filled. The default 1:1 shape:

1. Reader — one line: who, how technical, relationship, cares.
2. Open with — the framing sentence or two.
3. Credit — named people, specific contributions.
4. Where things stand — delivered, in the reader's register.
5. What I want them to know — strategic, 3–5 items.
6. Decisions or asks — what needs to happen in the room.
7. Ask them — questions, because a meeting is not a broadcast.
8. If asked — prepared short answers.
9. Footer — don't-raise list.

## Open questions (for the principal)

1. Length target per meeting type?
2. During-meeting capture: live notes surface, or paper?
3. Register samples: require 2–3 samples of the principal's own
   recent writing to a comparable reader before drafting?
4. Reader profiles: confirm the per-person file convention?
5. Disclosure line: confirm R9's upward-vs-forum default?
