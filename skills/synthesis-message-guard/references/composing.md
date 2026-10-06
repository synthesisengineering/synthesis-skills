# Composing under the guard

## Contents

- [Why it exists](#why-it-exists)
- [The honest workflow](#the-honest-workflow)
- [Before you ask for approval: the checklist](#before-you-ask-for-approval-the-checklist)
- [What the guard checks, and the words it blocks with](#what-the-guard-checks-and-the-words-it-blocks-with)
- [Email transports and their fields](#email-transports-and-their-fields)
- [Known limits — stated, not hidden](#known-limits--stated-not-hidden)
- [Related](#related)

## Why it exists

Two same-night incidents (2026-07-29), both by an agent that had the relevant
rules loaded in context:

1. **A reply composed without reading the thread it was replying into.** The
   thread's own quoted history contained the principal's earlier message taking
   the opposite strategic position, with a better argument. The reply was sent.
   Correcting it cost a follow-up email and real trust.
2. **A drafted message containing register patterns the principal's written
   voice rules explicitly ban** (self-flagellation about a delayed reply;
   expressing trust in a colleague via the author's own limitation). The
   principal had warned about exactly this class before.

Both failures were rule-knowledge failures at compose time, not knowledge gaps.
The fix is structural: make the send mechanically impossible until the work is
attested and the text passes a deterministic scan.

In v5 the attestation is the principal's own approval of the exact call, which is
stronger for wording than a ledger the composing agent wrote about itself. The research
the ledger used to force is now the agent's binding rule, below, because no approval can
see whether the thread was read.

A claim such as "still unanswered", "unsent", or "no reply yet" is a
statement about NOW that rests on a read taken at some moment. On 2026-09-01
a "still unanswered by the principal" claim resting on a read eight hours old
passed as verified while the answer had gone out that morning. Re-read the source
of any such claim within 30 minutes of sending; stable facts ("PR 96 merged") need no
re-read. An email thread once moved eight minutes after it was read
(2026-08-28): the pre-send re-read is its own act.

## The honest workflow

1. Read the FULL thread you are replying into — including quoted history.
   The thread's own tail is a primary source; a reply that contradicts it is
   the canonical incident.
2. Search prior correspondence for the recipient AND topic — every mailbox the
   principal uses, plus local transcripts. Record the queries.
3. Compose. Fix register hits by rewriting the thought, not by
   thesaurus-dodging the regex.
4. Map every factual claim to its source. A claim you cannot source becomes a
   question to the recipient or gets cut.
5. Freeze the complete tool call, including recipients, subject, alternate parts and
   threading fields. Make the call; fix anything the guard names; show the principal the
   exact text for approval; repeat the identical call once they approve.
6. Read the draft or sent message back through the transport, and record it.

## Before you ask for approval: the checklist

The 1.x ledger's attestations, now the agent's own check before showing the principal:

- **Reply status:** is this a reply? Then the source ids of every message actually read
  in the thread this session, and the history searches run (query, where, results).
- **Claims:** every factual claim mapped to a source, or none made. A currency claim
  carries the time its source was read, within 30 minutes.
- **Voice:** the principal's voice rules loaded and passed (the private writing-voice
  skill is the source of truth the register patterns derive from).
- **Invented precision:** every number in the text has a source.
- **Recipient address:** right person, right address, right account.
- **Branding:** for a send as the agent, the persona branding the correspondence skill
  requires.

## What the guard checks, and the words it blocks with

`guards.message_problems` runs before any approval is filed. Each failure is listed after
`This message can't go out as written:`.

| Check | Applies to | Message |
|---|---|---|
| Register scan of every string in the call, and of the text each HTML part renders (tags, entities and whitespace can't hide a phrase) | Every send | `message breaks the rule '<name>': <why>` |
| Threading headers (`in_reply_to`, `references`) | Every send | `... is HTML-escaped ...; a Message-ID takes literal angle brackets, <id@host>` / `... has an unbalanced angle bracket` |
| HTML required | Email | `email goes out as HTML, never plain text ...` |
| HTML markup: only p, div, span, a, em, strong, b, i, u, ul, ol, li, blockquote, html, body; attributes href, title, lang, dir; links https, http or mailto; balanced; no comments; no `<br>` | Email HTML parts | `<field>: unsupported HTML element <x>`, `a <br> breaks a paragraph ...` |
| `body_format: html` with no markup in the body | Workspace connector | `body_format is html but the body has no paragraph markup ...` |
| Markdown (`[x](https://...)`, `**bold**`, `# heading`) | Email bodies | `markdown never renders in email ...` |
| A line break inside a paragraph | Email plain parts; every chat message | `<field>: a line break falls inside a paragraph ...` |
| Persona signature shown as a bare domain | Any message carrying a configured persona marker | `the signature shows <domain> as text ...` |

Blank lines separate paragraphs. A line starting a list item (`-`, `*`, `•`, `+`, `1.`),
a quote (`>`) or a table row (`|`) starts its own line, and fenced code keeps its lines.
Slack mrkdwn (`*bold*`, `_italic_`, `<https://x|label>`) is fine in chat.

The approval binds the whole call: tool name and every input field, nested parts and
attachment references included, keyed by digest. Object-key ordering does not change
it; array ordering and any field change do. Two sessions composing different messages
get different codes and never share a slot (2026-09-02: a single shared slot let one
seat's write replace another's, and the refusal blamed an edit that never happened).

## Email transports and their fields

| Transport | Body fields | HTML |
|---|---|---|
| Google's Gmail connector: `create_draft`, `update_draft`, `send_message`, `reply`, `forward` | `htmlBody`; `body` (or `forwardText`) is the plain-text alternative | Pass `htmlBody`. Without it the email is plain text and blocks. |
| Workspace connector: `send_gmail_message`, `draft_gmail_message` | `body` with `body_format` | Pass `body_format: "html"`. Its default is plain. |
| Apple Mail `send_email` | `body`, plain text only | Blocks unless the principal lists it in `message_format.plain_email_tools`. |

A `send_message` tool counts as email when it carries `to`, `cc`, `bcc`, `subject`,
`htmlBody` or `body_format`; one that carries a `session_id` is a session-to-session
message and not correspondence at all.

## Known limits — stated, not hidden

- **Judgment failures pass the scan.** A condescending-but-pattern-free
  sentence, a strategically wrong recommendation, or a subtly mis-scoped legal
  claim will not trip a regex. Those are caught by the forced research step and,
  for high-stakes messages, by adversarial multi-agent review. The
  scan removes the *enumerable* failure modes; approval puts the principal's eyes
  on the exact text; neither replaces review.
- **Execution tools can invoke other transports.** The guard does not parse arbitrary shell programs or prove absence of network effects. Sending through an unapproved transport is prohibited; retain native sandbox/network controls and explicit communication authorization. Never classify a general execution tool as read-only from its name.
- **Hook config loads at session start.** A newly wired hook protects new
  sessions; the wiring session itself must self-enforce.

## Related

- `synthesis-git-hooks` — the same fail-closed philosophy at the commit
  boundary; this skill is its correspondence twin.
- The principal's private writing-voice skill — the source of truth the block
  patterns are derived from.
- [`synthesis-agent-correspondence`](../../synthesis-agent-correspondence/SKILL.md) — lanes,
  personas and the research gates this guard enforces the mechanical half of.
- `synthesis-agent-guardrails` — the account a mail or calendar call acts as, checked
  before the send guard so no approval is spent on the wrong account.
