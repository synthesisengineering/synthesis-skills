# Sending one approved iMessage

Read before any send, and after any outcome other than `dispatched`. The send is
`scripts/messages_send.py`: the v5 send guard (requirement R3.1) around one call
to the fixed Messages script `scripts/messages_transport.js`. It replaced the
0.1.0 coordinator, native owner and outbound readback in milestone M3; their
text is in [preserved.md](preserved.md).

## Before the command

- Draft from the conversation itself, read in Messages or with the reader, and
  follow the correspondence rules (synthesis-agent-correspondence and the
  principal's private voice rules). The principal approves the exact words and
  the exact recipient; a summary of the message is not approval.
- Write the approved text to a file in UTF-8, exactly as approved. One extra
  space is a different message and needs its own approval.
- The recipient is a handle: `+<country code><number>` or an email address.

## The command and the approval

```bash
python3 scripts/messages_send.py --to +15551234567 --text-file reply.txt [--account ACCOUNT_ID]
```

1. It refuses at once when an earlier attempt with this recipient and text
   exists, unless that attempt is known not to have reached the send call.
2. It finds the one existing one-to-one iMessage chat with the handle through
   `scripts/messages_route.js`, which only reads accounts and chats. No chat, or
   only an SMS account or a group, refuses: start the conversation in Messages
   first. Two matching accounts refuse until `--account` names one.
3. The send guard checks the principal's forbidden phrases from
   `~/.synthesis/v5/config.json`, then looks for their approval of this exact
   recipient and text. Without one, it prints `needs-approval` with a reason
   that names a six-character code. Show the principal the recipient and the
   text, and ask them to reply `approve <code>`. Only their own prompt grants
   it; it expires after 15 minutes and lets exactly one send through. Then run
   the identical command again.
4. It records the attempt as uncertain, then makes exactly one send call. The
   text travels to `messages_transport.js` through a private, already-unlinked
   file descriptor, never through argv or script source. The script checks the
   account, chat and participant again and expiry once more right before its
   single `send`.

An unreadable config, or a runtime that cannot be found, refuses: the send guard
fails closed.

## Outcomes

| status | exit | means | next |
|---|---|---|---|
| `dispatched` | 0 | The send call returned. Delivery and acknowledgement stay unknown. | Note it in the plan with the time. A repeat of the same text to the same person is refused. |
| `not-sent` | 3 | The fixed script stopped before its send call (for example the account went offline). | Fix the cause; the spent approval does not carry over, so the principal approves again. |
| `uncertain` | 3 | Anything else: a timeout, a lost process, an error after the call. It may have sent. | Never resend. Tell the principal; they check the conversation in Messages and send by hand if needed. |
| `refused` | 2 | Nothing was sent: no chat, a malformed request, a forbidden phrase, an earlier attempt. | Read the reason. |
| `needs-approval` | 2 | Nothing was sent. | Show the exact recipient and text; wait for `approve <code>`. |

A matching outbound row in the Messages database never upgrades `uncertain`:
the scripting interface returns no message identifier, and the principal may
have sent the same words by hand. The attempt record keeps the recipient, a hash
of the text and the outcome under `~/.synthesis/v5/state/imessage-sends/`, never
the text, and is dropped after 30 days.

## What the send never does

No WhatsApp sending, SMS or RCS fallback, chat creation, group send, recipient
alias lookup, retry, account discovery beyond the one handle, permission change,
or injected bridge. Required Apple Events permission and database access come
from ordinary platform controls. The synthetic tests run both fixed scripts
under a Node double of the scripting bridge; they do not exercise the real
Messages app, its permissions, a real account, delivery or read receipts.
