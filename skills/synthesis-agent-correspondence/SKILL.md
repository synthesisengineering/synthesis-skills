---
name: synthesis-agent-correspondence
description: >
  How AI agents compose and send correspondence — Slack, email, or any other channel — on a
  human principal's behalf, with disclosure strength scaled to how much the principal reviewed
  the exact text before it went out, never to abstract categories. Covers the three universal
  review tiers (reviewed, standing-direction, unreviewed-substantive), the default
  human-sends-it-themselves lane, a persona-registry config schema for branding one or more
  agent identities, the bot-vs-assistant archetype that sets a persona's default tone, channel
  disclosure facts (Slack forces a visible send-tag; most other channels don't), and the three
  compose/send gates that protect the work underneath the disclosure. Use when asked to: agent
  correspondence, message signature, disclosure tier, persona registry, send on my behalf,
  compose as my agent, standing-direction send, reviewed-tier send, ghostwriting disclosure,
  bot vs assistant persona, agent branding, outbound message gate.
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Agent Correspondence

## The core principle

Ghostwriters and executive assistants have drafted correspondence for the people they serve for as long as there has been correspondence to draft. An assistant who writes a letter that the principal then reads, edits if needed, and signs themselves has never been considered dishonest — because the principal owns the exact words before they go out under their name. Nobody appends "an assistant helped write this" to a letter the sender read and chose to send; there is nothing to disclose when the sender saw every word first.

The honesty question only bites when nobody reviewed the words before they went out. That single fact is the load-bearing idea behind this entire skill. Tiers, personas, channel behavior, gates — all of it is mechanism built on top of one rule:

> **Disclosure strength should scale with how much the principal reviewed the exact text before it was sent — never with how the work was categorized.**

## The three tiers

These apply when an agent, not the human, performs the send action. (When the human sends it themselves, see the next section — none of this applies.)

| Tier | When it applies | What the disclosure must say |
|---|---|---|
| `reviewed` | The human approved this exact text before it went out — per-message or in a batch | The agent's role in composing and sending, stated plainly |
| `standing_direction` | The agent sends per a standing rule/class the human set, not reviewed message-by-message | This one was handled on standing direction, and the human reads every reply |
| `unreviewed_substantive` | Substantive content sent before the human could review it — rare, and only under an explicit standing instruction that this is allowed at all | An explicit flag that the human hasn't reviewed the details yet and will follow up personally |

Hard content limits on `standing_direction` (not suggestions): never opinions, never commitments, never anything touching a sensitive relationship, never criticism — criticism is always personal and always reviewed. When a draft is ambiguous about which tier it belongs in, route it UP toward `reviewed`, never down toward `standing_direction`.

`unreviewed_substantive` is the exception case, not a normal operating mode. It should require its own explicit standing instruction to exist at all, separate from the general standing-direction instruction, and should stay rare enough that seeing it is itself a signal something time-sensitive is happening.

## The default lane: the human sends it themselves

Underneath all three tiers is a lane that isn't a tier at all: the human reviews the draft and clicks send personally. Regardless of how much AI assistance went into drafting, there is nothing to disclose on any channel — exactly like the ghostwritten letter the principal signs. This is usually the highest-volume, lowest-risk correspondence lane, and it should be the default recommendation for anything requiring personal voice or touching a relationship that matters. Build the surrounding tooling — drafts folders, review queues — so this lane is the easy path, not a fallback bolted on after the automated tiers.

## Routing heuristic

A rough but reliable filter for which lane a piece of correspondence belongs in:

- **Personal, relationship-significant, or opinion-bearing content** → the human sends it themselves.
- **Pure routing, scheduling, status-relay, or acknowledgment content with no opinion or commitment in it** → `standing_direction` fits well.
- **Everything in between** → `reviewed`.

`unreviewed_substantive` is never a routing target — it exists only for the rare case an explicit standing instruction creates; nothing should default into it.

## Persona registry — configuration, not skill content

This skill defines the mechanism; it doesn't know anyone's brand name. A user's actual agent personas belong in a private, source-controlled config, defined once and reused everywhere a persona might compose or send:

```yaml
personas:
  - id: acme-bot
    display_name: "Acme-Bot"
    archetype: bot            # bot | assistant — see below
    emoji: "🤖"
    url: "https://acme-bot.example/"
    scope: >
      Default persona for standing-direction sends across all channels.

  - id: acme-assistant
    display_name: "Acme-Assistant"
    archetype: assistant
    emoji: "🧞"
    url: "https://acme-assistant.example/"
    scope: >
      Personal-voice, reviewed-tier correspondence.
```

A fuller, commented template is in [`references/persona-registry.example.yaml`](references/persona-registry.example.yaml).

- **`id`** — stable internal identifier; never shown to recipients.
- **`display_name`** — exact prose spelling. Branding is absolute: pick one capitalization and one form, and never vary it in outgoing text.
- **`archetype`** — `bot` or `assistant` (below) — sets the persona's default signature register.
- **`emoji`** — the persona's visual marker. Personas should not share an emoji; it's the fastest signal a recipient has for which persona sent a message.
- **`url`** — the persona's reference link, if it has one.
- **`scope`** — a free-text hint for when to reach for this persona over another. A user can define as many personas as they want — one per venture, one for work correspondence and a different one for personal, or any other partition that matches how they actually operate — and different personas can be used for different kinds of correspondence.

### Archetype sets the tone, not just the icon

`archetype` decides who the signature line names as the actor — the single highest-leverage field in the schema.

- A **`bot`**-archetype persona's signature centers the **tool** as actor: the tool did the work, the human directed it. *"my Acme-Bot handled this for me."*
- An **`assistant`**-archetype persona's signature centers the **human** as actor, with the tool named as instrument: the human is still the one communicating, just working through a different tool. *"I wrote this with my Acme-Assistant."*

Same tier, same honesty, two registers:

| Archetype | A `reviewed`-tier signature |
|---|---|
| `bot` | `🤖 _composed and sent with my [Acme-Bot](https://acme-bot.example/)_` |
| `assistant` | `🧞 _I wrote this with my [Acme-Assistant](https://acme-assistant.example/)_` |

Both are fully honest about the tool's involvement. They differ only in where the reader's attention lands — on the tool's action or on the human's authorship. Match the archetype to how the persona is actually used: a persona that does a lot of unattended standing-direction work reads naturally as a `bot`; a persona used mainly for reviewed, personal-voice correspondence reads naturally as an `assistant`.

## Channel disclosure is a fact, not a preference

Whether a channel forces visible disclosure when an agent performs the send is a property of that channel — verify it, don't assume it.

- **Slack forces it.** Slack's own agent/bot connector auto-stamps a visible "Sent using [agent name]" tag the instant an agent, not the human, performs the send action. No signature wording removes or competes with this — it's platform-level, not composed text. Write the persona's own signature to pre-explain the platform tag, since it will appear regardless.
- **Most other channels don't.** Email a human sends by clicking "send" on an agent-drafted message carries no platform tag at all — the send action was human, full stop. A direct API send with no human click frequently carries no tag either, but that varies by provider. Where nothing is forced, disclosure is a genuine choice, governed by the tier table above, not by the channel.
- **Check, don't guess.** Connector behavior changes with product updates. Verify each channel's actual current behavior before designing a persona's signature around an assumption carried over from another channel, or from memory.

## Three gates

The tiers say *what* to disclose. These gates protect the *work* underneath the disclosure — a message can be honestly tiered and still be wrong, stale, or off-voice. All three are substance, not enforcement; `synthesis-message-guard` (below) is what makes them mechanical instead of optional.

### 1. Reply-history gate — before composing

Before drafting any reply, or any message that continues an existing topic: read the entire thread, including the quoted history under the latest message — the thread's own tail is a primary source, and every prior position the human took in it constrains what the reply may say. Search prior correspondence for the recipient AND the topic, across every mailbox and channel the human actually uses. A zero-result search is never evidence of absence — prove the search tool still works with a query known to return results before trusting any null.

### 2. Compose-time voice & anti-slop gate — before staging or presenting a draft

Load whatever voice/style skill governs the human's correspondence register before writing a word — their own private voice rules, or an organization's general writing-quality skills (`synthesis-content-quality` and `synthesis-writing-pitfalls` are the general-purpose public catalogs for this: AI-cadence patterns, disproportionate praise, apology overuse, aphorism-pivot closers). Grounding is necessary but not sufficient — a factually accurate draft that reads as slop still damages the relationship the message exists to serve.

### 3. Pre-send relevance & grounding gate — at send time

Approval of text is not approval of staleness. Immediately before transmitting: re-read the target thread or channel live — never from local transcripts alone — and check whether anyone has replied or moved the topic since composing. Re-verify every factual claim the message makes. A draft that has been sitting in an approval queue or drafts folder for more than about a day needs a full re-gate, not a glance. The verdict is always one of three: send, revise, or withdraw.

## Adopting this for yourself

1. **Define your persona(s)** in a private, source-controlled config, using the schema above with your real names, emoji, and URLs.
2. **Pick an archetype per persona** based on how it is actually used, not how you'd like it to be used.
3. **Verify your channels' real disclosure behavior** rather than assuming from this skill's Slack example.
4. **Write your `standing_direction` content limits.** The hard limits above (no opinions, no commitments, no sensitive relationships, no criticism) are a floor — add whatever else is specific to your context.
5. **Wire the three gates to your own voice/style skill(s)**, and to `synthesis-message-guard` if you want fail-closed enforcement rather than a convention that depends on being remembered.
6. **Keep the private layer thin.** It should hold only what's actually yours — names, exact signature wording, org-specific routing rules — and reference this skill for the mechanism. Duplicating the mechanism into the private layer is how the two drift apart.

## Related

- [`synthesis-message-guard`](../synthesis-message-guard/SKILL.md) — the mechanical enforcement layer: a fail-closed pre-send hook that blocks a send unless a fresh grounding ledger attests the gates above actually ran. This skill states the conventions; message-guard is what makes them impossible to skip.
- [`synthesis-content-quality`](../synthesis-content-quality/SKILL.md) and [`synthesis-writing-pitfalls`](../synthesis-writing-pitfalls/SKILL.md) — the detection catalogs behind the compose-time voice gate.
- [`synthesis-writing-craft`](../synthesis-writing-craft/SKILL.md) — the positive craft principles underneath any drafted correspondence.
- [`synthesis-disclosure-policy`](../synthesis-disclosure-policy/SKILL.md) — a sibling config-driven pattern (a published-precedent ledger instead of a persona registry) for the adjacent question of what may be said about real parties, rather than who's speaking.

A private companion configuration — the user's actual persona registry, exact signature wording, and any organization-specific rules layered on top (assignment routing, approval-phase state, team-specific content limits) — belongs in their private skill collection. This public skill carries the mechanism only.
