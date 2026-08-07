---
name: synthesis-agent-correspondence
description: >
  How AI agents compose and send correspondence — Slack, email, or any other channel — on a
  human principal's behalf, honestly. The model is three lanes on one axis, how much of the
  principal is in the words: principal-direct (their words, their hands — no disclosure),
  assistant-lane (their words, the agent's hands — a single authorship signature), and bot-lane
  (their direction, the agent's words — a handled-for-me signature). Review depth (exact-text /
  per-message directive / standing direction / autonomous) is internal governance, not
  recipient-facing disclosure. Covers the persona-registry config schema, the binding
  bot-vs-assistant archetype, channel disclosure facts (Slack forces a visible send-tag; most
  other channels don't), and the three compose/send gates. Use when asked to: agent
  correspondence, message signature, disclosure lane, persona registry, send on my behalf,
  compose as my agent, standing-direction send, my words vs my direction, ghostwriting
  disclosure, bot vs assistant persona, agent branding, outbound message gate.
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
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
| **Bot lane** | The agent's, under the principal's direction — per-message instruction or standing rules | The agent | **A handled-for-me signature**: the named agent handled this under the principal's direction, and the principal reads every reply. Wording may reflect how deep the direction ran. |

The lanes are peers on a ladder, not tiers of one system stacked on another. A recipient who has seen two or three messages learns the legend without being taught:

> **No marker — all the principal. Assistant marker — the principal's words, the agent's hands. Bot marker — the principal's direction, the agent's words.**

That legend is the product. Every design choice below exists to keep it learnable and never false.

### The assistant lane requires exact-text ownership

The assistant lane's signature makes a strong claim: *these are my words.* That claim is only honest when the principal composed the text, dictated it, or edited it to the point of genuine ownership — the modern equivalent of dictating to a staff member who types, fixes the grammar, and sends. Light agent cleanup (spelling, formatting, threading) does not break ownership, exactly as a typist's corrections never did.

**A message the principal has not made their own cannot use the assistant lane. This is a category error, not a wording problem** — no signature phrasing can honestly combine "these are my words" with "I did not review these words." When a message needs to go out without that ownership, it belongs in the bot lane, whose signature claims direction rather than authorship. (This rule exists because the failure was discovered in practice: attempts to write an "unreviewed" variant of an assistant-lane signature come out self-contradictory every time. The cell is impossible; delete the cell.)

### The bot lane spans direction depths

The bot lane honestly covers everything from "the principal told the agent what to say and glanced at the result" to "the agent acted on standing rules" to — where a principal explicitly builds toward it — "the agent read the incoming message and handled it." What varies across that range is internal governance (next section), not the lane. The signature always claims the same two things: the agent produced the words under the principal's direction, and the principal sees the replies.

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

### Archetype is binding — it selects the lane, not just the tone

`archetype` is the schema's highest-leverage field, and in this skill's first version it only set the signature's register. That undersold it. The archetype **is** the lane assignment:

- An **`assistant`**-archetype persona exists for assistant-lane sends only. Its signature centers the principal as author, the tool as instrument — *"I wrote this with my Acme-Assistant"* — and it has **one** signature, because the lane has one meaning. Using it requires exact-text ownership, always.
- A **`bot`**-archetype persona exists for bot-lane sends. Its signature centers the tool as actor under direction — *"my Acme-Bot handled this one for me — I read every reply"* — and may carry variants reflecting review depth, since the lane honestly spans several.

Generic signature examples:

| Lane / depth | Example signature |
|---|---|
| Assistant lane (always `exact_text`) | `🧞 _I wrote this with my [Acme-Assistant](https://acme-assistant.example/)_` |
| Bot lane, `exact_text` approved | `🤖 _composed and sent with my [Acme-Bot](https://acme-bot.example/)_` |
| Bot lane, `standing_direction` | `🤖 _my [Acme-Bot](https://acme-bot.example/) handled this one for me — I read every reply_` |
| Bot lane, sent ahead of review (rare) | `🤖 _drafted by my [Acme-Bot](https://acme-bot.example/) at my direction — I haven't reviewed the details yet and will follow up myself_` |

## Channel disclosure is a fact, not a preference

Whether a channel forces visible disclosure when an agent performs the send is a property of that channel — verify it, don't assume it.

- **Slack forces it.** Slack's agent/bot connector auto-stamps a visible "Sent using [agent name]" tag the instant an agent, not the human, performs the send. No signature wording removes it — it's platform-level. Write the persona's signature to pre-explain the tag, since it will appear regardless.
- **Most other channels don't.** Email the human sends by clicking "send" on an agent-drafted message carries no platform tag — the send action was human. A direct API send frequently carries none either, but that varies by provider. Where nothing is forced, disclosure is governed by the lane, not the channel.
- **Check, don't guess.** Connector behavior changes with product updates. Verify each channel's current behavior before designing a signature around an assumption carried from another channel, or from memory.

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

## Migrating from v1 of this skill

v1 organized everything around three review tiers as the recipient-facing system, with archetype as tone. v2 inverts that: the **lane** (principal-direct / assistant / bot) is the recipient-facing system, review depth is internal governance, and archetype is binding. If you built on v1: your `reviewed`/`standing_direction`/`unreviewed_substantive` tiers map directly onto the review-depth column (`exact_text` / `standing_direction` / bot-lane-ahead-of-review), your bot persona's signatures carry over unchanged, and the only breaking change is that an assistant persona now has exactly one signature — its former standing-direction and unreviewed variants were incoherent cells, and any traffic that used them belongs to the bot persona.

## Related

- [`synthesis-message-guard`](../synthesis-message-guard/SKILL.md) — the mechanical enforcement layer: a fail-closed pre-send hook that blocks a send unless a fresh grounding ledger attests the gates above actually ran. This skill states the conventions; message-guard is what makes them impossible to skip.
- [`synthesis-content-quality`](../synthesis-content-quality/SKILL.md) and [`synthesis-writing-pitfalls`](../synthesis-writing-pitfalls/SKILL.md) — the detection catalogs behind the compose-time voice gate.
- [`synthesis-writing-craft`](../synthesis-writing-craft/SKILL.md) — the positive craft principles underneath any drafted correspondence.
- [`synthesis-disclosure-policy`](../synthesis-disclosure-policy/SKILL.md) — a sibling config-driven pattern (a published-precedent ledger instead of a persona registry) for the adjacent question of what may be said about real parties, rather than who's speaking.

A private companion configuration — the user's actual persona registry, exact signature wording, and any organization-specific rules layered on top (assignment routing, approval-phase state, team-specific content limits) — belongs in their private skill collection. This public skill carries the mechanism only.
