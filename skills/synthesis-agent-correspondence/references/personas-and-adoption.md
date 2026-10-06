# Personas, signatures, adoption and migration

How a principal configures personas and their signatures, how to adopt this skill, and how to migrate from v1 or v2, as written in 3.1.2.

Contents:
- Persona registry: the schema and each field
- Archetype is binding: lane and narrator, with example signatures
- Adopting this for yourself: six steps
- Migrating from earlier versions: v1 to v2, v2 to v3

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

A fuller, commented template is in [`references/persona-registry.example.yaml`](persona-registry.example.yaml).

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

## Adopting this for yourself

1. **Define your persona(s)** in a private, source-controlled config, using the schema above with your real names, emoji, and URLs — at minimum one `bot` persona; add an `assistant` persona when you want an agent to transmit words that are genuinely yours.
2. **Treat the archetype as law.** The assistant persona never signs words you don't own; the bot persona never claims words are yours.
3. **Verify your channels' real disclosure behavior** rather than assuming from this skill's Slack example.
4. **Write your `standing_direction` content limits.** The hard limits above are a floor — add whatever else is specific to your context.
5. **Wire the three gates to your own voice/style skill(s)**, and configure `synthesis-message-guard` (its register patterns live in the principal's config) if you want fail-closed enforcement — a register scan and the principal's approval of each exact call — rather than a convention that depends on being remembered. If your register patterns include brand-integrity rules, make them lane-aware: block each persona's emoji when its own branding is absent, rather than banning an emoji outright.
6. **Keep the private layer thin.** It should hold only what's actually yours — names, exact signature wording, org-specific routing rules — and reference this skill for the mechanism. Duplicating the mechanism into the private layer is how the two drift apart.

## Migrating from earlier versions of this skill

**v1 → v2.** v1 organized everything around three review tiers as the recipient-facing system, with archetype as tone. v2 inverts that: the **lane** (principal-direct / assistant / bot) is the recipient-facing system, review depth is internal governance, and archetype is binding. Your `reviewed`/`standing_direction`/`unreviewed_substantive` tiers map directly onto the review-depth column (`exact_text` / `standing_direction` / bot-lane-ahead-of-review); the only breaking change is that an assistant persona has exactly one signature — its former standing-direction and unreviewed variants were incoherent cells, and any traffic that used them belongs to the bot persona.

**v2 → v3.** v2 had bot personas write in the principal's first person, disclosing agency only in the signature. v3 binds voice to archetype: bot personas speak as themselves, assistant personas as the principal. Three consequences for adopters. (1) Bot signatures rewrite from the principal's voice ("my Acme-Bot handled this…") into the persona's ("I'm Acme-Bot, Alex's AI assistant…") — one narrator per message. (2) Sincerity classes (appreciation, kudos, condolences, relationship-touching messages) leave the bot lane: their value requires the principal's own voice, so they route to principal-direct or assistant even when low-stakes. (3) If a fail-closed register guard bans third-person agent phrasing wholesale (a v2-era rule), retarget it to servile relay-framing only ("Alex would like me to…", "on behalf of Alex" as an opener) — plain statements about the principal are now the bot lane's canonical voice, and an unretargeted guard will block every compliant send.
