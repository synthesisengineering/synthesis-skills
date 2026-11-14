---
name: synthesis-message-guard
description: "Send guard for agent-drafted messages: no send or draft goes out until the principal approves that exact call, and the text passes the register scan and format rules (HTML email, whole paragraphs, linked signatures, literal Message-IDs). Use when composing, configuring, or when a send is blocked."
license: "Apache-2.0"
depends_on: ["synthesis-agent-correspondence"]
metadata:
  author: "Rajiv Pant"
  version: "2.11.1"
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
10. **Call people by the name they go by.** When the call carries an identifier the principal lists under `preferred_names` (an address, a Slack user or DM id), that person's official first name in the text is refused; mention syntax and address fields stay as the platform needs them (2026-10-13).
11. **Every channel is guarded, by what a call does** (2026-10-13). A connector tool whose name delivers words (send, reply, comment, post, share, or creating or editing an issue, page, message or review) and a shell command that posts (`gh` and `bkt` comments and PR writes, their `api` writes, `curl`/`wget`/HTTPie writes to another host) wait for the code; work in the principal's `own_repos` does not. A program that sends some other way is still a send the guard cannot see: ask first.
12. **Computer use and the browser are guarded too** (2026-10-22). In a messaging app (WhatsApp, Messages, Slack, Mail, Teams and more) and on a messaging site (Google Chat, Gmail, WhatsApp Web, Messenger, every page of facebook.com, Instagram, LinkedIn and X, and more), a click on Send, a Return in the compose field, a typed line break, the Send menu item or shortcut, a page script that acts and a click with no `action_summary` wait for the code. In any app or page so does a click whose summary says it sends or publishes ("Submits the review", a click on Post, Comment, Reply, Share or Submit), unless it only opens or closes a box, signs in or searches; on any page, so do typed words then Return where the call names a post, and a script that submits. Words typed in a messaging app or site pass the register scan as they are typed. Write each summary as what the action does, type the words and send in one call where you can (the approval binds both), and show the principal a screenshot of the compose area with the code.
13. **A send window is the principal's setting, never yours.** `synthesis sends open --hours N --sends M --channels ...` (at most 12 hours and 50 planned sends; the last one closes it) needs their code; inside it, a send in a covered channel that carries a `send_window_signatures` signature goes without a per-message code, after the same register scan and format rules, and is logged. `synthesis sends close` ends it; `synthesis sends log` lists the day's sends for "On your behalf".
14. **A meeting placed on today has an approval of its own** (2026-11-09). With `same_day_meetings` in the config, a calendar write that starts today and invites anyone but the principal waits for a code typed for that same-day meeting; the ordinary invitation approval and a send window do not cover it. An exempt attendee keeps the ordinary approval, and a hold with no attendees is untouched. Propose another day unless the principal asked for today.
15. **A calendar write that puts the principal at a place carries its travel line** (2026-11-11). With `in_person_travel` in the config, such a write is refused until the event's description says how they get there. It asks for no approval (references/config.md).
16. **An address that can change never goes to a person** (2026-11-12). With `temporary_addresses` in the config, a send, draft, shell post or typed words holding a quick tunnel's host, or an address only this machine or its network answers, are held before the message's approval is asked: only the principal's code for those addresses releases them, and the message then still needs its own; starting a quick tunnel waits for a code of its own.
17. **A time in a message rests on a fresh calendar read** (2026-11-12). With `fresh_calendar` in the config, a message to a person whose words name a clock time is held unless this session read a calendar, successfully, within its `minutes` (10 unless set, 1 to 60), or the principal types the hold's own code, which stands for the ordinary one. In Codex, Muse and a sub-agent the guard sees no calendar read, so only that code releases it (references/config.md).

## Contents

- [references/procedure.md](references/procedure.md): compose, check, approve, send, verify. Read every time.
- [references/composing.md](references/composing.md): why the guard exists, the honest workflow, every check with the words it blocks with, the email transports' fields, and known limits. Read before composing a message the guard will see, and when a send is blocked.
- [references/config.md](references/config.md): the config keys, the example config, calibration and the positive controls. Read when setting up or changing the guard's config.
- [references/coverage-map.md](references/coverage-map.md): where every part of 1.8.0 lives now (ruling D8).
- [references/preserved.md](references/preserved.md): what was not kept and why, with the 1.8.0 text verbatim. Read only to review the cut.

## Procedure

Compose, check, approve, send, verify and record, step by step: [references/procedure.md](references/procedure.md). Read it every time.
