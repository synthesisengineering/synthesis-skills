---
name: synthesis-agent-correspondence
description: "Compose and send honest agent correspondence on Slack, email and other channels: principal-direct, assistant and bot lanes, the voice axis, review depth, personas, disclosure signatures and send gates. Use for sending on a principal's behalf, message signatures, persona registries or agent voice."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "4.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Agent Correspondence

How an agent drafts and sends correspondence for a principal honestly: which lane a message belongs in, who narrates it, what its signature discloses, and the gates it passes before it leaves.

> **Disclosure should answer the one question the recipient actually cares about: whose words are these? Everything else — how the sausage was made, what approval workflow ran — is internal governance, not disclosure.**

## Binding rules

1. **Every message sits in one lane.** Principal-direct carries no marker; the assistant lane (the principal's words, the agent's hands) carries one authorship signature; the bot lane (the principal's direction, the agent's words) carries the persona's own signature.
2. **The assistant lane requires exact-text ownership.** Words the principal has not made their own go in the bot lane: no signature can honestly say both "these are my words" and "I did not review these words."
3. **The archetype binds the narrator.** An assistant persona writes in the principal's first person; a bot persona says "I" for itself and names the principal in the third person, early. One narrator per message.
4. **Sincerity classes route up.** Appreciation, kudos, condolences and relationship messages need the principal's voice: would it sound right coming from a staff assistant? If not, route up.
5. **Hard content limits at `standing_direction` and deeper:** never opinions, commitments, sensitive relationships or criticism. Add limits; never subtract these.
6. **When in doubt, claim less.** Approval doubt routes toward more review; authorship doubt routes to the bot lane. A false assistant-lane signature cannot be walked back.
7. **Personas live in a private registry.** Branding is absolute, and a persona's emoji never appears on another persona's message.
8. **Channel disclosure is a fact, not a preference.** Verify each channel's current behavior; Slack stamps agent-performed sends whatever the signature says.
9. **Signature links render natively per channel,** as the section below sets out.
10. **Pass the three gates.** Read the whole thread and prior correspondence before composing; load the voice and anti-slop rules before drafting; re-read the live thread and re-verify every claim at send time. The verdict is send, revise or withdraw.
11. **Bind and verify every send.** Load `synthesis-message-guard` for construction and the ledger, and verify the actual raw readback after an authorized draft or send.

## Contents

- [references/lanes-and-voice.md](references/lanes-and-voice.md): the core principle, the three lanes, the voice axis and bot-voice composition rules, and review depth with its content limits and routing rules. Read it before choosing a lane or writing in a persona's voice.
- [references/gates-and-sending.md](references/gates-and-sending.md): channel disclosure, the three gates in full, email construction and verification, related skills. Read it before composing a reply and again at send time.
- [references/personas-and-adoption.md](references/personas-and-adoption.md): the persona registry schema, archetype binding with example signatures, adoption steps, and migration from v1 and v2. Read it when configuring personas or writing a signature.
- [references/persona-registry.example.yaml](references/persona-registry.example.yaml): a commented registry template. Read it when creating a registry.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 3.1.2 text now lives.
- Signature links render natively per channel: below.

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
