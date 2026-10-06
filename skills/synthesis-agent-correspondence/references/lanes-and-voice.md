# Lanes, voice and review depth

The doctrine behind every message, as written in 3.1.2: why disclosure tracks whose words a message carries, the three lanes, the voice axis that binds the narrator to the archetype, and review depth as internal governance.

Contents:
- The core principle
- The two questions, and the three lanes: the assistant lane requires exact-text ownership; the bot lane spans direction depths
- The voice axis (v3.0.0): the staff analogy, why it is enforced, the upgraded legend, bot-voice composition rules
- Review depth: the four depths, the hard content limits, the two routing rules

## The core principle

Ghostwriters and executive assistants have drafted correspondence for the people they serve for as long as there has been correspondence to draft. Senior executives have long run their correspondence through personal staff at several levels of involvement at once: some messages the principal writes personally; some the principal dictates and staff transmit; some the principal directs at a high level ("reply warmly, decline the date") and staff compose in the principal's voice; and some the staff handle entirely, with the principal's knowledge of the system rather than of the message. None of that was ever considered dishonest, and none of it carried a disclaimer — because the principal owned the relationship and the direction, and the staff were a trained extension of the principal's judgment.

AI agents change two things about that old system, and only two. First, some platforms stamp agent-performed sends visibly, so pretending is not even an option. Second, an AI agent is not yet as reliable as a trained human staff — a hallucinated detail attributed to the principal's own hand damages trust in everything the principal actually wrote. So unlike the human-staff era, disclosure is warranted. The design question is what the disclosure should track.

> **Disclosure should answer the one question the recipient actually cares about: whose words are these? Everything else — how the sausage was made, what approval workflow ran — is internal governance, not disclosure.**

## The two questions, and the three lanes

Every outgoing message answers two questions: **whose words are these**, and **who performed the send**. Those two answers sort all correspondence into three lanes on a single axis — how much of the principal is in the words:

| Lane | Whose words | Who sends | Recipient-facing disclosure |
|---|---|---|---|
| **Principal-direct** | The principal's | The principal | **None.** Nothing to disclose, on any channel — regardless of how much AI research, drafting, or polish went into it. The principal read every word and performed the send; that is the ghostwritten letter the principal signs. |
| **Assistant lane** | The principal's — composed, dictated, or edited to the point of genuine ownership | The agent | **A single authorship signature**: the principal wrote this, working through the named agent. One line, one meaning, no variants. |
| **Bot lane** | The agent's, under the principal's direction — per-message instruction or standing rules | The agent | **The persona's own signature**: the named agent introduces itself, states the principal's direction, and promises the principal reads every reply. Wording may reflect how deep the direction ran. The body speaks in the persona's own voice (see the voice axis below). |

The lanes are peers on a ladder, not tiers of one system stacked on another. A recipient who has seen two or three messages learns the legend without being taught:

> **No marker — all the principal. Assistant marker — the principal's words, the agent's hands. Bot marker — the principal's direction, the agent's words.**

That legend is the product. Every design choice below exists to keep it learnable and never false.

### The assistant lane requires exact-text ownership

The assistant lane's signature makes a strong claim: *these are my words.* That claim is only honest when the principal composed the text, dictated it, or edited it to the point of genuine ownership — the modern equivalent of dictating to a staff member who types, fixes the grammar, and sends. Light agent cleanup (spelling, formatting, threading) does not break ownership, exactly as a typist's corrections never did.

**A message the principal has not made their own cannot use the assistant lane. This is a category error, not a wording problem** — no signature phrasing can honestly combine "these are my words" with "I did not review these words." When a message needs to go out without that ownership, it belongs in the bot lane, whose signature claims direction rather than authorship. (This rule exists because the failure was discovered in practice: attempts to write an "unreviewed" variant of an assistant-lane signature come out self-contradictory every time. The cell is impossible; delete the cell.)

### The bot lane spans direction depths

The bot lane honestly covers everything from "the principal told the agent what to say and glanced at the result" to "the agent acted on standing rules" to — where a principal explicitly builds toward it — "the agent read the incoming message and handled it." What varies across that range is internal governance (next section), not the lane. The signature always claims the same two things: the agent produced the words under the principal's direction, and the principal sees the replies.

## The voice axis — the archetype also binds the narrator (v3.0.0)

The lane says whose words a message carries. The voice axis says who **speaks** — and the two
must agree, because the grammatical person of a message is a disclosure the recipient reads in
every sentence, whether or not it was designed as one.

**The staff analogy that decides it.** A chief of staff is authorized to speak *as* the
principal: drafts go out in the principal's first person, under the principal's ownership. An
executive assistant speaks in their own voice *for* the principal's office: "Alex is traveling
this week; I've moved your 2:00." Both are honest, both are centuries-old convention, and
recipients parse each instantly. The archetypes map onto exactly this split:

- An **`assistant`**-archetype persona is the chief of staff. Its messages are written in the
  **principal's first person**, because the entry condition of its lane is that the words ARE
  the principal's. "I" means the principal.
- A **`bot`**-archetype persona is the executive assistant. Its messages are written in the
  **persona's own voice**: the persona says "I" about itself and refers to the principal by
  name, in the third person. It writes in the register the principal trained it to use — the
  principal's clarity, brevity, and style rules — minus the principal's "I."

**The analogy honors these professions; it does not replace them.** Chiefs of staff and
executive assistants are skilled roles this system borrows its conventions from precisely
because they work. A principal who has a human chief of staff or EA should expect these
personas to make that person more effective — absorbing the mechanical load so the human's
judgment, relationships, and taste go further. A principal who has neither gets a working
approximation of support they otherwise lack entirely. In both cases the agent extends the
office; it does not compete with anyone in it.

**Why this is worth enforcing rather than leaving to taste:**

1. **Grammar is the disclosure that survives.** Signatures are the most skippable part of a
   message — truncated in previews, dropped from forwards, cut from quoted replies. A message
   written in the persona's own voice is self-disclosing in every sentence; no excerpt of it
   can silently impersonate the principal.
2. **It creates an error-absorption layer, which widens safe autonomy.** When an assistant's
   note gets a detail wrong, the social reading is "the assistant got it wrong; the principal
   will fix it." When a first-person "I" message is wrong, the principal said something false.
   The riskier a mistake in the principal's own mouth, the narrower the autonomous lane must
   be — so the persona's own voice is what lets `standing_direction` carry more. Ownership
   never transfers (the principal answers for the system), and the hard content limits do not
   loosen; only the social cost of a routine error drops.
3. **It protects the currency of the principal's first person.** When every sentence that says
   "I" was genuinely owned by the principal, the "I" stays meaningful. Bot-lane messages that
   perform the principal's voice on unreviewed words quietly debase it.

**The upgraded legend — pronouns become the protocol:**

> **First person ⟺ the principal's ownership (principal-direct or assistant lane). The
> persona's own voice ⟺ the agent's words (bot lane).** The signature confirms what the
> grammar already said.

**Bot-voice composition rules:**

- The persona says "I" for itself and names the principal in the third person. Establish the
  narrator **early** — a reference to the principal by name in the first sentence or two —
  never only in the signature, since the message arrives from the principal's own account.
- For a recipient who has never seen the persona, open with one identifying clause ("This is
  Acme-Bot, Alex's AI assistant —"). Identification is not a process banner: what stays
  banned is apologetic process-framing as the opener, not a staff member saying who they are.
- The persona relays facts, logistics, and decisions the principal actually made. It never
  characterizes the principal's unstated opinions or feelings ("Alex thinks…", "Alex would be
  happy to…" — says who?), never negotiates substance, and escalates rather than improvises.
- **Sincerity classes require the principal's voice.** Appreciation, kudos, condolences, and
  anything whose value is the personal relationship lose their worth through an intermediary —
  "Alex appreciates the quick turnaround" is distinctly colder than "thank you." Those route
  to the principal-direct or assistant lane even when low-stakes. This yields the practical
  lane test: **would it sound right coming from a staff assistant? If not, route up.**

## Review depth — internal governance, not disclosure

Review depth is the approval-workflow axis: what has to happen before a message may leave. It determines gates, content limits, and logging. It is deliberately **not** the recipient-facing taxonomy — recipients care whose words they are reading, not which internal approval path ran.

| Review depth | What it means | Lanes it can feed |
|---|---|---|
| `exact_text` | The principal approved (or authored) this exact text | Principal-direct, assistant lane, or bot lane |
| `per_message_directive` | The principal gave a specific instruction for this message ("reply affirmatively, propose Tuesday") but did not necessarily see the final words | Bot lane only |
| `standing_direction` | The agent sends per standing rules the principal set for a class of messages, with no per-message involvement | Bot lane only |
| `autonomous_initiative` | The agent notices the need and handles it end to end — the deepest form of the old staff system, where the principal knows the system, not the message | Bot lane only; requires its own explicit standing instruction to exist at all, and per-send logging the principal actually reads |

**Hard content limits at `standing_direction` and deeper** (floors, not suggestions): never opinions, never commitments, never anything touching a sensitive relationship, never criticism — criticism is always personal and always reviewed. Add your own limits on top; never subtract these.

**Two routing rules, one for each direction of doubt:**

- **Approval doubt routes toward more review.** Not sure whether a message is safe for `standing_direction`? It goes to per-message review.
- **Authorship doubt routes toward the weaker claim.** Not sure the principal genuinely owns the words? It's the bot lane. **When in doubt, claim less.** An assistant-lane signature on words the principal didn't own is the one failure this system cannot walk back, because it falsifies the legend the recipient has learned.
