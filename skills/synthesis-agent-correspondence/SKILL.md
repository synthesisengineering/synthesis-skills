---
name: synthesis-agent-correspondence
description: >
  Compose and send honest agent correspondence across Slack, email, and other channels. Defines
  principal-direct, assistant, and bot lanes; the voice axis (chief-of-staff personas speak as
  the principal, executive-assistant personas speak as themselves); review-depth governance;
  persona configuration; disclosure signatures; and compose/send gates. Use for agent
  correspondence, sending on a principal's behalf, message signatures, disclosure lanes, persona
  registries, agent branding, agent voice, third-person agent messages, standing-direction
  sends, ghostwriting disclosure, or outbound-message gates.
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "3.1.1"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Agent Correspondence

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

## Persona registry — configuration, not skill content

This skill defines the mechanism; it doesn't know anyone's brand name. A user's actual agent personas belong in a private, source-controlled config:

```yaml
personas:
  - id: acme-bot
    display_name: "Acme-Bot"
    archetype: bot            # binding: this persona carries bot-lane semantics
    emoji: "🤖"
    url: "https://acme-bot.example/"
    scope: >
      All bot-lane sends: the agent's words under my direction — routing,
      scheduling, status, acknowledgments, and directed replies.

  - id: acme-assistant
    display_name: "Acme-Assistant"
    archetype: assistant      # binding: this persona carries assistant-lane semantics
    emoji: "🧞"
    url: "https://acme-assistant.example/"
    scope: >
      Assistant-lane sends only: my words, transmitted by my agent.
      Exact-text ownership required — no exceptions.
```

A fuller, commented template is in [`references/persona-registry.example.yaml`](references/persona-registry.example.yaml).

- **`id`** — stable internal identifier; never shown to recipients.
- **`display_name`** — exact prose spelling. Branding is absolute: one capitalization, one form, never varied in outgoing text.
- **`archetype`** — `bot` or `assistant`. **Binding, not cosmetic** (below).
- **`emoji`** — the persona's visual marker; this is the legend, so personas must never share one, and a persona's emoji never appears on another persona's message.
- **`url`** — the persona's reference link, if it has one.
- **`scope`** — free text describing when this persona is used. Define as many personas as match how you actually operate — one per venture, separate work and personal identities, multiple bot brands for different audiences. Every persona still maps to exactly one lane via its archetype.

### Archetype is binding — it selects the lane and the narrator, not just the tone

`archetype` is the schema's highest-leverage field. In this skill's first version it only set
the signature's register; v2 made it the lane assignment; v3 makes it bind the narrator too:

- An **`assistant`**-archetype persona exists for assistant-lane sends only. The body is the
  principal's first person, and its signature centers the principal as author, the tool as
  instrument — *"I wrote this with my Acme-Assistant"* — **one** signature, because the lane
  has one meaning. Using it requires exact-text ownership, always.
- A **`bot`**-archetype persona exists for bot-lane sends. The body is the persona's own
  voice, and its signature is written the same way — the persona introducing itself and
  making the loop-closing promise on the principal's behalf. It may carry variants reflecting
  review depth, since the lane honestly spans several. One narrator per message: a bot-voice
  body with a principal-voice signature flips the narrator mid-message, and recipients notice.

Generic signature examples (a principal named Alex):

| Lane / depth | Example signature |
|---|---|
| Assistant lane (always `exact_text`) | `🧞 _I wrote this with my [Acme-Assistant](https://acme-assistant.example/)_` |
| Bot lane, `exact_text` approved | `🤖 _I'm [Acme-Bot](https://acme-bot.example/), Alex's AI assistant — Alex approved this message before I sent it_` |
| Bot lane, `standing_direction` | `🤖 _I'm [Acme-Bot](https://acme-bot.example/), Alex's AI assistant, sent under standing direction — Alex reads every reply_` |
| Bot lane, sent ahead of review (rare) | `🤖 _I'm [Acme-Bot](https://acme-bot.example/), Alex's AI assistant — Alex hasn't reviewed the details yet and will follow up personally_` |

## Channel disclosure is a fact, not a preference

Whether a channel forces visible disclosure when an agent performs the send is a property of that channel — verify it, don't assume it.

- **Slack forces it.** Slack's agent/bot connector auto-stamps a visible "Sent using [agent name]" tag the instant an agent, not the human, performs the send. No signature wording removes it — it's platform-level. Write the persona's signature to pre-explain the tag, since it will appear regardless.
- **Most other channels don't.** Email the human sends by clicking "send" on an agent-drafted message carries no platform tag — the send action was human. A direct API send frequently carries none either, but that varies by provider. Where nothing is forced, disclosure is governed by the lane, not the channel.
- **Check, don't guess.** Connector behavior changes with product updates. Verify each channel's current behavior before designing a signature around an assumption carried from another channel, or from memory.

## Signature links render natively per channel (v3.1.0)

The persona's name in a signature is a **named hyperlink on every channel that can
render one**. A visible URL is the last-resort fallback for channels that genuinely
cannot — never a stylistic choice, because the raw-URL form costs exactly the
recipients the signature exists to serve.

Link capability is a per-channel fact, verified against the actual send path like
disclosure behavior above:

- **Slack** renders `<https://example.com/|Name>` mrkdwn as a true link.
- **Email renders HTML, never markdown.** `[Name](url)` in an email body is
  literal text to every mail client. The signature (and therefore the whole body)
  must go out as an HTML part — `<a href="https://example.com/">Name</a>` — via
  whatever the send tool exposes (an html body format, or a dedicated html-body
  parameter). When the tool takes both a plain and an html part, the html part
  carries the anchor and the plain part carries the fallback form. A plain-text
  body is not a softer version of the same signature: the receiving client
  auto-links the raw URL and may wrap it in a tracking redirect, so the recipient
  sees neither the clean name-link nor the clean URL. (Observed live: a
  markdown-authored signature reached Gmail as plain text and displayed as the
  name followed by a provider-redirect URL in parentheses.)
- **Rich editors** (docs, wikis) take the platform's native link on the name.
- **Channels with no rich text on the send path** (for example Google Chat
  messages sent with user credentials, where named-link markup is app-only) use
  the plain fallback: `Name (example.com)` — short and readable as text, chosen
  for how it reads, not for auto-linking.

Markdown link syntax remains the *notation* for drafts, approval prompts, and
review surfaces; the wire format is the channel's own. Converting notation to the
channel form is part of staging the send, and a compose gate should treat
markdown reaching an email body as a defect, not a fallback.

**The send path is part of the channel (v3.1.1).** Two tools for the same
mailbox can store different bytes: a tool that takes structured fields and lets
the provider compose the message server-side may rewrite your hrefs (observed
live: Gmail's composer wrapping every link in an expiring `google.com/url`
redirect at ingestion), while a tool that submits raw MIME stores the bytes you
built. When both exist, prefer the byte-faithful path — and verify a path once
by reading the stored message back in raw form before trusting it with real
correspondence. A link that looks right in the client can still be wrapped
underneath; only the stored bytes settle it.

## Three gates

The lanes say *what* to disclose. These gates protect the *work* underneath the disclosure — a message can be honestly labeled and still be wrong, stale, or off-voice. All three are substance, not enforcement; `synthesis-message-guard` (below) is what makes them mechanical instead of optional.

### 1. Reply-history gate — before composing

Before drafting any reply, or any message that continues an existing topic: read the entire thread, including the quoted history under the latest message — the thread's own tail is a primary source, and every prior position the principal took in it constrains what the reply may say. Search prior correspondence for the recipient AND the topic, across every mailbox and channel the principal actually uses. A zero-result search is never evidence of absence — prove the search tool still works with a query known to return results before trusting any null.

### 2. Compose-time voice & anti-slop gate — before staging or presenting a draft

Load whatever voice/style skill governs the principal's correspondence register before writing a word — their own private voice rules, or the general-purpose public catalogs (`synthesis-content-quality` and `synthesis-writing-pitfalls`: AI-cadence patterns, disproportionate praise, apology overuse, aphorism-pivot closers). Grounding is necessary but not sufficient — a factually accurate draft that reads as slop still damages the relationship the message exists to serve. This gate matters most in the bot lane, where the agent's words carry the principal's name; in the assistant lane the principal's own authorship is the voice gate.

### 3. Pre-send relevance & grounding gate — at send time

Approval of text is not approval of staleness. Immediately before transmitting: re-read the target thread or channel live — never from local transcripts alone — and check whether anyone has replied or moved the topic since composing. Re-verify every factual claim the message makes. A draft that has been sitting in an approval queue or drafts folder for more than about a day needs a full re-gate, not a glance. The verdict is always one of three: send, revise, or withdraw.

## Adopting this for yourself

1. **Define your persona(s)** in a private, source-controlled config, using the schema above with your real names, emoji, and URLs — at minimum one `bot` persona; add an `assistant` persona when you want an agent to transmit words that are genuinely yours.
2. **Treat the archetype as law.** The assistant persona never signs words you don't own; the bot persona never claims words are yours.
3. **Verify your channels' real disclosure behavior** rather than assuming from this skill's Slack example.
4. **Write your `standing_direction` content limits.** The hard limits above are a floor — add whatever else is specific to your context.
5. **Wire the three gates to your own voice/style skill(s)**, and to `synthesis-message-guard` if you want fail-closed enforcement rather than a convention that depends on being remembered. If your guard has brand-integrity patterns, make them lane-aware: block each persona's emoji when its own branding is absent, rather than banning an emoji outright.
6. **Keep the private layer thin.** It should hold only what's actually yours — names, exact signature wording, org-specific routing rules — and reference this skill for the mechanism. Duplicating the mechanism into the private layer is how the two drift apart.

## Migrating from earlier versions of this skill

**v1 → v2.** v1 organized everything around three review tiers as the recipient-facing system, with archetype as tone. v2 inverts that: the **lane** (principal-direct / assistant / bot) is the recipient-facing system, review depth is internal governance, and archetype is binding. Your `reviewed`/`standing_direction`/`unreviewed_substantive` tiers map directly onto the review-depth column (`exact_text` / `standing_direction` / bot-lane-ahead-of-review); the only breaking change is that an assistant persona has exactly one signature — its former standing-direction and unreviewed variants were incoherent cells, and any traffic that used them belongs to the bot persona.

**v2 → v3.** v2 had bot personas write in the principal's first person, disclosing agency only in the signature. v3 binds voice to archetype: bot personas speak as themselves, assistant personas as the principal. Three consequences for adopters. (1) Bot signatures rewrite from the principal's voice ("my Acme-Bot handled this…") into the persona's ("I'm Acme-Bot, Alex's AI assistant…") — one narrator per message. (2) Sincerity classes (appreciation, kudos, condolences, relationship-touching messages) leave the bot lane: their value requires the principal's own voice, so they route to principal-direct or assistant even when low-stakes. (3) If a fail-closed register guard bans third-person agent phrasing wholesale (a v2-era rule), retarget it to servile relay-framing only ("Alex would like me to…", "on behalf of Alex" as an opener) — plain statements about the principal are now the bot lane's canonical voice, and an unretargeted guard will block every compliant send.

## Related

- [`synthesis-message-guard`](../synthesis-message-guard/SKILL.md) — the mechanical enforcement layer: a fail-closed pre-send hook that blocks a send unless a fresh grounding ledger attests the gates above actually ran. This skill states the conventions; message-guard is what makes them impossible to skip.
- [`synthesis-content-quality`](../synthesis-content-quality/SKILL.md) and [`synthesis-writing-pitfalls`](../synthesis-writing-pitfalls/SKILL.md) — the detection catalogs behind the compose-time voice gate.
- [`synthesis-writing-craft`](../synthesis-writing-craft/SKILL.md) — the positive craft principles underneath any drafted correspondence.
- [`synthesis-disclosure-policy`](../synthesis-disclosure-policy/SKILL.md) — a sibling config-driven pattern (a published-precedent ledger instead of a persona registry) for the adjacent question of what may be said about real parties, rather than who's speaking.

A private companion configuration — the user's actual persona registry, exact signature wording, and any organization-specific rules layered on top (assignment routing, approval-phase state, team-specific content limits) — belongs in their private skill collection. This public skill carries the mechanism only.
