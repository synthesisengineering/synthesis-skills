# Sending one approved message

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
4. It records the attempt as uncertain, then makes exactly one send call (two with a photo). The
   text travels to `messages_transport.js` through a private, already-unlinked
   file descriptor, never through argv or script source. The script checks the
   account, chat and participant again and expiry once more right before its
   first `send`.

An unreadable config, or a runtime that cannot be found, refuses: the send guard
fails closed.

## A group or an SMS chat, by its members (2026-10-20)

```bash
python3 scripts/messages_send.py --members +15551234567,+15557654321 --text-file post.txt [--service iMessage|SMS] [--account ACCOUNT_ID]
```

`--members` names an existing chat by exactly its members: the one iMessage or
SMS chat, group or one-to-one, whose people are those handles and nobody else.
It was built for a trip's SMS group the principal set up with two friends, so an
agent could post logistics there under the same approval as any other send.

- The route script reads every connected iMessage and SMS account and keeps
  only chats whose member handles equal the set given, in any order. None
  refuses; two (say an iMessage group and an SMS group with the same people)
  refuse until `--service` or `--account` picks one. It never creates a chat,
  never moves a chat to another service, and never uses RCS.
- The approval binds every member, the chat's service, the text and the chat
  itself, and the code request names all of them: show the principal the
  members, the service and the exact text. Approving one set of members covers
  no other set.
- Right before its single send call, the transport script checks the account
  and its service again and requires the chat's members to equal the approved
  ones, each by identity and handle. Anyone added or removed since then stops
  the send as `not-sent` with `participants changed`, and a new approval is
  needed.
- Outcomes, the record and the never-resend rule are the same as above.

For monitoring the same group, see `watched_chats` in
[adapter-contract.md](adapter-contract.md): the reader then keeps every message
in that chat as a note, not only the ones that name the principal.

## A photo, alone or with a caption (2026-10-22)

```bash
python3 scripts/messages_send.py --to +15551234567 --photo dinner.jpg --text-file caption.txt
```

The principal's ruling on 2026-10-22: iMessage and SMS photos send directly, under the same approval. `--photo`
works with `--to` or `--members`, and `--text-file` may be left out for a photo alone.

- One photo per send: `.jpg`, `.jpeg`, `.png`, `.heic`, `.heif`, `.gif` or `.webp`, at most 100 MB.
- The approval names the photo by its name, size and SHA-256 along with the text and recipient, so a
  different photo, or the same one edited, needs its own approval. Show the principal the photo itself (open
  it) as well as the text before asking for the code.
- The packet carries the photo's path, size and change time, never its bytes. Just before sending, the
  transport checks that size and change time again; a photo edited since it was read stops the send as
  `not-sent` with `attachment changed`, and the principal approves the new one.
- The photo goes first and the text after it, as its caption: two send calls in one attempt. When the photo's
  call returns and the text's fails, the outcome is `uncertain`, never resent: the principal checks Messages and
  sends the caption by hand if it is missing.
- A text-only send keeps the record key it had before photos, so its earlier attempts still refuse a repeat.

## WhatsApp: a prefill the principal sends (2026-10-22)

WhatsApp's Mac app has no scripting interface, and the principal ruled that an agent prepares the message and
they press Send. `scripts/whatsapp_prefill.py` does exactly that much:

```bash
python3 scripts/whatsapp_prefill.py --to +15551234567 --text-file reply.txt [--photo dinner.jpg]
```

- It opens `whatsapp://send` with the number and the exact text, once. Nothing is sent, so no approval code is
  asked for: the principal reads the text in WhatsApp and presses Send. With `--photo` it also shows the photo
  in Finder to drag into the chat.
- It refuses a number with no one-to-one chat in WhatsApp's database (it never starts a chat), found by the
  number's own id or by the linked id WhatsApp may keep instead, and reads chat sessions and linked ids only,
  never messages. A link cannot name a group, so groups are never prefilled. Text is at most 4,096 characters.
- Stop at the prefill. A Send pressed by computer use afterwards is a send, and the send guard holds it for a
  code (5.1.5); the ruling is that the principal presses it.

## Outcomes

| status | exit | means | next |
|---|---|---|---|
| `dispatched` | 0 | Every send call returned; `parts` names them (`photo`, `text`). Delivery and acknowledgement stay unknown. | Note it in the plan with the time. A repeat of the same text to the same person is refused. |
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

No WhatsApp sending (only the prefill above, which sends nothing), fallback between iMessage and SMS, RCS,
chat creation, a group reached by anything but exactly its members, recipient alias lookup, retry,
account discovery beyond the chats with the handles given, permission change, or
injected bridge. Required Apple Events permission and database access come
from ordinary platform controls. The synthetic tests run both fixed scripts
under a Node double of the scripting bridge; they do not exercise the real
Messages app, its permissions, a real account, delivery or read receipts.
