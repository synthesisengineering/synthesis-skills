---
name: synthesis-message-guard
description: "Send guard for agent-drafted messages: no send or draft goes out until the principal approves that exact call, and the text passes the register scan and format rules (HTML email, whole paragraphs, linked signatures, literal Message-IDs). Use when composing, configuring, or when a send is blocked."
license: "Apache-2.0"
depends_on: ["synthesis-agent-correspondence"]
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Message Guard

Prose rules do not survive contact with a model under load. This skill is the
enforcement layer for correspondence the way commit hooks are the enforcement
layer for repositories: the rules live in code, run outside the model, and fail
closed. The v5 PreToolUse hook runs `guards.check_send` on every Slack, Gmail, email,
chat and draft tool call: the text must pass the principal's register scan and the
format rules, and then the principal must approve that exact call.

## Binding rules

1. **The principal approves the exact call.** A blocked send files a request with a six-character code; only the principal typing `approve <code>` in their own prompt grants it (the harness's transcript must show it), for one identical call within 15 minutes. Never grant one yourself. Any change after approval (a recipient, cc, bcc, subject, thread, any body part, an attachment) needs a new approval.
2. **Do the research approval can't check.** Read the whole thread, quoted history included; search earlier correspondence with the recipient and topic in every mailbox and local transcript; map every factual claim to a source or turn it into a question; re-read the source of any "still unanswered", "unsent" or "no reply yet" claim within 30 minutes of sending (2026-07-29, 2026-09-01).
3. **Email is HTML,** each paragraph in its own `<p>`, with no `<br>` or line break inside a paragraph and no markdown. Plain-text email is never acceptable output: it is hard-wrapped on send (2026-09-23 ruling). Only a transport the principal lists as plain-only may send plain text, and its paragraphs stay whole.
4. **No text a person reads breaks a paragraph,** on any channel. List items, quotes, table rows and code blocks keep their lines.
5. **A persona signature is a link** wherever links render: the persona name is the hyperlink, never a bare domain beside it (2026-08-30).
6. **Threading headers carry literal Message-IDs,** `<id@host>`, never HTML-escaped and never with an unbalanced bracket (2026-08-20, 2026-08-28).
7. **Fix a register hit by rewriting the thought,** not by dodging the pattern. A rule that blocks the principal's own voice is miscalibrated, not strict (2026-08-03).
8. **After an approved draft or send, read it back** through the transport and confirm the recipients and paragraphs landed intact. A clean draft is not a clean send.
9. **Fail closed, narrowly.** An unreadable config blocks every send; session-to-session messages are never treated as correspondence.

## Contents

- **Procedure** (below): compose, check, approve, send, verify.
- [references/composing.md](references/composing.md): why the guard exists, the honest workflow, every check with the words it blocks with, the email transports' fields, and known limits. Read before composing a message the guard will see, and when a send is blocked.
- [references/config.md](references/config.md): the config keys, the example config, calibration and the positive controls. Read when setting up or changing the guard's config.
- [references/coverage-map.md](references/coverage-map.md): where every part of 1.8.0 lives now (ruling D8).
- [references/preserved.md](references/preserved.md): what was not kept and why, with the 1.8.0 text verbatim. Read only to review the cut.

## Procedure

1. **Research, then compose** (binding rule 2). Write email as HTML paragraphs: `htmlBody` on the Gmail connector (its `body` is the plain-text alternative, also whole paragraphs), `body` with `body_format: "html"` on the workspace connector.
2. **Freeze the complete call:** recipients, subject, thread fields, every body part, attachments. Then make the call once. If the text breaks a rule, the guard answers `This message can't go out as written: <reasons>.` and files nothing; fix it and call again.
3. **Ask for approval.** A clean message is blocked with `Sending needs the principal's approval of this exact message ... type approve followed by the code <code>`. Show the principal the exact text and recipients, in full, and the code. `synthesis approvals` lists what is waiting.
4. **When they type `approve <code>`,** make the identical call again. A changed call needs a new code; an approval unused after 15 minutes is gone, and so is one the harness declined after the guard let it through (references/composing.md).
5. **Verify** (binding rule 8): fetch the draft or sent message and compare recipients, subject and paragraphs with what was approved.
6. **Record** the send where the correspondence skills say (transcript, plan), with its message id.
