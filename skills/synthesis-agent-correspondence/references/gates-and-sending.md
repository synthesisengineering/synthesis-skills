# Channels, gates and sending

What each channel discloses on its own, the three gates every message passes, how email and other posts are built and verified, and the related skills, as written in 3.1.2. Signature-link rendering stays in SKILL.md.

Contents:
- Channel disclosure is a fact, not a preference
- Three gates: reply history before composing, voice and anti-slop before drafting, relevance and grounding at send time
- Email construction and verification, and other human-readable posts
- Related

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

## Email construction and verification

Use HTML paragraphs by default and avoid rendered line breaks inside prose
paragraphs. The principal may explicitly choose plain text or intentional line
structure through the message-guard owner's formatting policy. This choice
never changes authorship lanes, exact-text approval, disclosure or recipient
checks. Follow the principal's private transport restrictions when present.

Load `synthesis-message-guard` for construction, capability enrollment and the
complete tool-input ledger. Ground every populated alternate part; bind the
final recipients, subject, body, thread fields and tool name with `--message-sha`.
After an authorized draft/send, verify its actual raw readback and preserve the
message ID and provenance. Do not call a synthetic MIME roundtrip a native send,
a filed draft or delivery confirmation. Route catalog changes to the existing
configuration owner, preserving unrelated hooks and non-email workflows.


Other human-readable correspondence follows the same overridable default for
paragraphs. Use `--build-text` for literal prose and `--verify-text-readback`
after an authorized post. Intentional code, poetry and address blocks require
an owner-approved paragraph-policy override; never normalize significant
whitespace. Retain post IDs, retrieval evidence and any missing-readback gap.

## Related

- [`synthesis-message-guard`](../../synthesis-message-guard/SKILL.md) — the mechanical enforcement layer: a fail-closed pre-send hook that blocks a send unless a fresh grounding ledger attests the gates above actually ran. This skill states the conventions; message-guard is what makes them impossible to skip.
- [`synthesis-content-quality`](../../synthesis-content-quality/SKILL.md) and [`synthesis-writing-pitfalls`](../../synthesis-writing-pitfalls/SKILL.md) — the detection catalogs behind the compose-time voice gate.
- [`synthesis-writing-craft`](../../synthesis-writing-craft/SKILL.md) — the positive craft principles underneath any drafted correspondence.
- [`synthesis-disclosure-policy`](../../synthesis-disclosure-policy/SKILL.md) — a sibling config-driven pattern (a published-precedent ledger instead of a persona registry) for the adjacent question of what may be said about real parties, rather than who's speaking.

A private companion configuration — the user's actual persona registry, exact signature wording, and any organization-specific rules layered on top (assignment routing, approval-phase state, team-specific content limits) — belongs in their private skill collection. This public skill carries the mechanism only.
