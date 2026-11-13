# Composing under the guard

## Contents

- [Why it exists](#why-it-exists)
- [The honest workflow](#the-honest-workflow)
- [Before you ask for approval: the checklist](#before-you-ask-for-approval-the-checklist)
- [What the guard checks, and the words it blocks with](#what-the-guard-checks-and-the-words-it-blocks-with)
- [Email transports and their fields](#email-transports-and-their-fields)
- [Approval: only the principal's own prompt](#approval-only-the-principals-own-prompt)
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
- **The form:** for a send through a web form or an app's dialog, read how the form takes
  its input before staging the send: one value to a field, how several recipients are
  entered, what a field accepts. A form that refuses the input after the approval has
  spent the code for nothing (five addresses typed into one field were rejected once the
  code was used, 2026-11-12).
- **Names:** everyone the text greets or names is called by the name they go by
  (`synthesis-agent-correspondence` binding rule 12). The guard catches only the
  people the principal's `preferred_names` lists, when the call identifies them.
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
| A person's official first name (whole word, case-sensitive), outside the address fields | Any message whose call carries one of that person's `preferred_names` identifiers (an address, a Slack user or DM id) | `this message involves someone who goes by <preferred>; write <preferred>, not <official>` |
| An attachment the connector would not attach as given: its file under any key but `path`, or none of `path`, `content` and `url`; two of the three; `content` with no `filename` or not in standard base64; an empty `url`; a `url` that is the connector's own download link (`/attachments/<id>`, with no host or on any host, since the hosts it serves are in its own settings), or one it does not fetch (anything but http or https with a host, a `file://` URL among them); an entry carrying `error` or `_resolved_bytes`, keys the connector writes into an entry itself (with `error` it leaves the entry out); a `filename` or `mime_type` with a control character or not given as text (it takes line breaks and NULs out of a filename, so the mail would go under another name, and fails the entry otherwise); a `content_id` its own rule refuses; or `attachments` in a shape it refuses (anything but a list of entries or the JSON text of one) | Workspace connector: `send_gmail_message`, `draft_gmail_message` | ``attachment <n> has none of `path`, `content` and `url` ...``, ``... gives `url` and `path`: the mail connector reads only the `url` ...``, ``... gives `content` with no `filename` ...``, ``... gives `content` that is not standard base64 ...``, ``... has an empty `url` ...``, ``... gives the `url` <url>, which the mail connector reads as its own download link ... from a file it saved on this disk, bytes an approval cannot bind: copy the file into <outbox> ...``, ``... the mail connector fetches a `url` only over http or https from a named host, so it would attach nothing ...``, ``attachment <n> carries `error`, which the mail connector sets on an entry itself ...``, ``attachment <n> gives `filename` '<name>' with a control character, or not as text ...``, ``attachment <n> gives the `content_id` '<id>', which the mail connector refuses ...``, `` `attachments` is neither a list of entries nor the JSON text of one ...``, `attachment <n> is not an object ...` |
| A file the connector would not read: the path is not whole, names no file, or lies outside the outbox and the connector's default attachment folder (`~/.workspace-mcp/attachments`; what the session's own process has in `ALLOWED_FILE_DIRS` adds nothing, since a connector started elsewhere carries its own); or its name or folder marks secrets; or one of the four `file_path` tools is given a file's content twice (two of `content`, `file_path`, `file_url`, `base64_content`: `the connector takes exactly one source`) | Workspace connector: an attachment's `path` in the two mail tools; `file_path` (a path or a `file://` URL) in `update_drive_file`, `import_to_google_doc`, `import_to_google_sheets` and `import_to_google_slides`; `fileUrl` as a `file://` URL in `create_drive_file` | `the attachment <path> is outside the folders the mail connector reads: copy the file into <outbox> ..., and file this send again` (or `is not a full path`, `does not exist`, `is not a file`, `is one the mail connector never reads ...`); for a Drive tool, `the file <path> is outside the folders the connector reads: ... and make this call again` |
| A file the call names that cannot be read when the call is made, or that the guard cannot hash in 2 seconds | The same tools, in a call that waits for a code | `the attachment <path> cannot be read (<why>)` |

A Drive tool that asks for no code (the three imports and `create_drive_file`) is
refused the same way, after `This call can't go as written:`.

Blank lines separate paragraphs. A line starting a list item (`-`, `*`, `•`, `+`, `1.`),
a quote (`>`) or a table row (`|`) starts its own line, and fenced code keeps its lines.
Slack mrkdwn (`*bold*`, `_italic_`, `<https://x|label>`) is fine in chat.

The approval binds the whole call: tool name and every input field, nested parts and
attachment references included, keyed by digest. Object-key ordering does not change
it; array ordering and any field change do. Two sessions composing different messages
get different codes and never share a slot (2026-09-02: a single shared slot let one
seat's write replace another's, and the refusal blamed an edit that never happened).

For a file the workspace connector reads from its own disk (an attachment's `path`, a
Drive tool's `file_path` or `file://` `fileUrl`), the digest also takes in the hash of
that file's bytes, read when the code is asked for and again when the call is made. A
file replaced in between needs a new approval, and the request ends `The approval covers
each file the call has the connector read as it is now, so name those files to the
principal too: one changed before the call needs a new code.` The read is bounded,
because a harness passes over a hook that runs past its time.

## Email transports and their fields

| Transport | Body fields | HTML |
|---|---|---|
| Google's Gmail connector: `create_draft`, `update_draft`, `send_message`, `reply`, `forward` | `htmlBody`; `body` (or `forwardText`) is the plain-text alternative | Pass `htmlBody`. Without it the email is plain text and blocks. |
| Workspace connector: `send_gmail_message`, `draft_gmail_message` | `body` with `body_format` | Pass `body_format: "html"`. Its default is plain. |
| Apple Mail `send_email` | `body`, plain text only | Blocks unless the principal lists it in `message_format.plain_email_tools`. |

A `send_message` tool counts as email when it carries `to`, `cc`, `bcc`, `subject`,
`htmlBody` or `body_format`; one that carries a `session_id` is a session-to-session
message and not correspondence at all.

The workspace connector reads an attachment given as a `path` from its own disk, and only
from the folders it was started to read, so a file is staged in the outbox
(`~/.synthesis/v5/outbox`) before the call is made. A path is judged as the connector
reads it: whole (no `~`, nothing relative), links followed, letters as written. Standard
base64 `content` with a `filename` is not a file read, and neither is a `url` the
connector fetches over http or https from a named host. A `url` that is its own download
link (`/attachments/<id>`, what its Drive and Gmail download tools hand back) is a file
read: it takes the bytes from a file it saved on this disk, which no approval binds, so
the guard refuses it and asks for that file's path, staged in the outbox. It fetches a
`url` only over http or https, so one of any other kind (a `file://` URL, a bare path)
attaches nothing and is refused the same way. Only what the connector reads counts as attached: a file under any other key
is not read at all. Its Drive tools read a local file under the same rule. The rule, its
reason and each refusal are in `synthesis-agent-correspondence`,
references/gates-and-sending.md.

## Approval: only the principal's own prompt

A clean message is blocked with `Sending needs the principal's approval of this exact
message. Show them the exact text and recipient and ask them to type approve followed by
the code <code>. Then make this identical call again.` The message never prints
"approve" and the code together, and no hook text does, so nothing an agent or a tool
echoes can stand in for the principal's words.

**Several calls, one message.** The principal can type the word once and the codes after it
on the same line, separated by spaces, commas or "and": `approve <code> <code> <code>`. Each
code grants its own call. The list ends at the first thing that is not a code and at the end
of the line, so a code mentioned later in the sentence, or pasted on the next line,
approves nothing. A negation before the word ("don't approve ...", "why not approve ...")
approves nothing either. When several calls wait, ask for them together: show each exact text and recipient,
then the codes in one line.

**Nothing typed is passed over without a word.** The next turn names every code that did not
take: `Not granted: no pending request has the code ...` for one that had expired, been used
or been mistyped, and `Not granted: the pending code ... is in the message, but not in a
list right after the word` for one that is waiting and was not approved (a new line, another
word, a negation or a tagged block came between). Tell the principal which ones did not take. Until 2.6.1
only a code that directly followed the word was read; on 2026-11-11 nine codes typed after
one "approve" granted one call and passed over eight without a word.

The principal's prompt is the only thing that grants. On 2026-10-05 (the M5 sandbox) an
agent granted its own send by piping a made-up prompt into the prompt hook, because the
agent runs as the same OS user as the hooks and a grant was only a file. Now the grant is
used only when the harness's own transcript of the session shows the principal typing
approve and that code after the request was filed. Tool output, hook text, compaction
summaries, subagent prompts and messages from other sessions never count. When the
transcript does not show it, the call stays blocked with that reason and the request is
filed again, with the code to show the principal.

The shell guard refuses the natural routes to a forgery: a command carrying a pending
code, one that runs the synthesis hook by hand, and one that writes into the synthesis
state folder or a harness's transcripts. Never try any of them; an approval that did not
come from the principal is not an approval.

**Why a second approval is sometimes asked.** The approval is spent when the guard lets
the call through, before the harness's own permission prompt or MCP approval policy. If
the harness or the principal then declines the call (Codex with `approval_policy =
never`, or a declined permission prompt), the approval is gone and the identical call
asks again. That is deliberate: a single-use approval fails safe. Tell the principal
why the code changed. A second code is also asked when a file the call names changed
after the approval, which covered the bytes the file had then.

## Known limits — stated, not hidden

- **Judgment failures pass the scan.** A condescending-but-pattern-free
  sentence, a strategically wrong recommendation, or a subtly mis-scoped legal
  claim will not trip a regex. Those are caught by the forced research step and,
  for high-stakes messages, by adversarial multi-agent review. The
  scan removes the *enumerable* failure modes; approval puts the principal's eyes
  on the exact text; neither replaces review.
- **Execution tools can invoke other transports.** The guard does not parse arbitrary shell programs or prove absence of network effects. Sending through an unapproved transport is prohibited; retain native sandbox/network controls and explicit communication authorization. Never classify a general execution tool as read-only from its name.
- **Computer use is judged by what each action shows.** In a messaging app a Return, a typed line
  break and a click with no summary are held mechanically; beyond those, a click counts as a send
  by its `action_summary`, so a summary that hides a send, a page script that submits a form, and
  pasted text go unseen (config.md, "Computer use and the browser"). Write summaries as what the
  action does; the binding rule covers the rest.
- **Hook config loads at session start.** A newly wired hook protects new
  sessions; the wiring session itself must self-enforce.
- **A same-user agent can still forge on purpose.** An agent that deliberately writes a
  line shaped like the principal's prompt into its harness's transcript, injects a prompt
  through the harness's own CLI with a code it assembles at run time, or rewrites the
  runtime under `~/.synthesis/v5`, gets past checks that run as the same OS user. The
  layers, what each stops, and what stays open are in the plugin's
  `docs/runtime-integration.md` (Approvals). Closing that needs the agent under its own
  OS user or sandbox.

## Related

- `synthesis-git-hooks` — the same fail-closed philosophy at the commit
  boundary; this skill is its correspondence twin.
- The principal's private writing-voice skill — the source of truth the block
  patterns are derived from.
- [`synthesis-agent-correspondence`](../../synthesis-agent-correspondence/SKILL.md) — lanes,
  personas and the research gates this guard enforces the mechanical half of.
- `synthesis-agent-guardrails` — the account a mail or calendar call acts as, checked
  before the send guard so no approval is spent on the wrong account.
