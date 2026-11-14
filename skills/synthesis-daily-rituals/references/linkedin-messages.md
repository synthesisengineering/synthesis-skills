# LinkedIn messages as a declared surface

Read before a sync in a workspace that declares `.agents/linkedin-sync.yaml`. `<rituals>` is this skill's folder;
`<W>` is the workspace. Messenger's chat list is read the same way, with its own script: its section, [Messenger's
chat list](#messengers-chat-list), closes this file; read it before a sync in a workspace that declares
`.agents/messenger-sync.yaml`.

## Why it is a surface of its own

LinkedIn reaches a mailbox only as notification emails, which often hide the text and never cover InMail or the
messages LinkedIn chooses not to email about. A principal found messages there that no ritual had shown him. The
conversation list itself shows what a ritual needs without opening anything: who, the day, who spoke last, the whole
last message, unread counts and LinkedIn's own "Reply?" nudge.

## The declaration

```yaml
# .agents/linkedin-sync.yaml
workspace: personal
inboxes: [focused, other]            # the inboxes to read; both when left out
```

## The address

**Never load `https://www.linkedin.com/messaging/` itself:** it opens the newest conversation by itself, and when
that one is unread the read marks it read. The read opens the new-message view,
`https://www.linkedin.com/messaging/thread/new/`: the same list on the left, an empty composer on the right, and
no conversation opened. Nothing is typed into the composer. A conversation's own address shows the list too, but
a conversation set aside for the read to open can gain a new message, which the read would then mark read.

There are two inboxes. **Focused** is the one the page opens with. **Other** is where LinkedIn files messages from
people the account is not connected to (message requests, recruiters, some InMail); on the page it sits behind
the menu on the "Focused" button, and nothing announces what arrives there. It has an address of its own,
`https://www.linkedin.com/messaging/thread/new/?inboxType=SECONDARY`, so reading it needs no click. The first
live read of it found conversations no ritual had shown.

Once the page has loaded, check two things before reading: the address still starts
`https://www.linkedin.com/messaging/thread/new/`, and no entry in the list is marked as the active conversation. If LinkedIn sent the page to a conversation, that
conversation was opened: `parse` counts and names it, and the plan says so.

## The read

1. `python3 <rituals>/scripts/linkedin_messages.py plan --config .agents/linkedin-sync.yaml` prints, per inbox,
   the address to open and the day to scroll back to: the day the last read reached, or two weeks back for a
   first read.

   ```text
   open  https://www.linkedin.com/messaging/thread/new/  (focused, in the new-message view: the list beside an empty composer; never the bare messaging page)
   read  focused: read through 2026-11-10; scroll back to that day, stop there, and pass --inbox focused --since 2026-11-10
   open  https://www.linkedin.com/messaging/thread/new/?inboxType=SECONDARY  (other, in the new-message view: ...)
   read  other: never read; scroll back to 2026-10-28, stop there, and pass --inbox other --since 2026-10-28
   ```

   Steps 2 to 5 are done once for each inbox, with its own address, its own day and its own watermark target.

2. Open that address in the browser profile where the principal is signed in to LinkedIn. Scroll the conversation
   list (the left pane, not the page) one screen at a time, and look at the oldest entry's day after each step.
   **Stop as soon as it is on or before the day `plan` named.** The list loads older conversations for as long as
   it is scrolled, so a script that scrolls "to the bottom" never arrives: on the first live read one loaded more
   than 500 conversations in about a minute before it was stopped. Click no conversation.
3. Save the list's text to a file: the list element's text where the browser tool can run a page script, or the
   whole page's text where it returns that. Note the time of the read.
4. `python3 <rituals>/scripts/linkedin_messages.py parse --text <file> --read-at <ISO time> --inbox <inbox> --since
   <day>` prints the coverage line and the conversations that end with someone else:

   ```text
   LinkedIn messages, focused: 8 conversations read from the list, back to 2026-11-05; 5 end with someone else (3 unread, LinkedIn asks for a reply on 1); none opened
     2026-11-10 Cy Castillo: Cy: We met years ago. Would you have thirty minutes to talk about a product role?
     2026-11-09 Eli Edwards: Eli: 👍  [LinkedIn asks for a reply]
     2026-11-06 Flo Fischer: InMail • Advisory project: how it works  [InMail, 1 unread]
   ```

   A conversation the list marks as open is counted as opened and named on a line of its own, under the coverage
   line. Exit 0: the read is complete. Exit 1: it stopped short of `--since` or could not read an entry; scroll
   further or look at the entry, and read again. Exit 2: the text holds no conversation list, or shows a sign-in page or a
   security check. **At a sign-in page, a security check or any warning from LinkedIn, stop and tell the principal.**
   An inbox with nothing in it: when the page itself says the inbox holds no conversations, save the whole page's
   text and pass `--empty`, which makes a complete read of none. Without the flag that text is refused, because
   a page saved before its list loaded looks the same; with it, a text that does hold conversations is refused.
   `--json` gives every conversation (`who`, `last`, `from_me`, `speaker`, `kind`, `unread`, `nudge`, `open`,
   `preview`), the `inbox` and the coverage (`threads`, `oldest`, `since`, `opened`, `unreadable`, `complete`,
   `through`).
5. Record the read: `python3 <rituals>/scripts/sync_watermark.py advance --workspace <W> --surface linkedin --target
   <inbox> --through <read time> --coverage <the --json output>`. The watermark moves only with a complete read's
   coverage, as a local message store's does.
6. The coverage line goes in the plan's sync state, word for word. It names no one.

## What is owed

The candidates are the conversations that end with someone else. From each preview:

- A thank-you or a reaction to the principal's own message is closed. Say so in one line; it needs nothing.
- Anything that asks, offers or invites goes to the plan with its day and the whole last message.
- An unread count, an InMail and LinkedIn's "Reply?" nudge are reasons to look, not verdicts.
- Open a thread only when the preview cannot show whether something is owed. Opening marks it read, so name each
  opened conversation in the plan and pass their number as `--opened`.

A reply is a send like any other: it goes through the correspondence skill, in the lane and with the signature rule
the principal has set for that site, and the send guard holds it for the principal's code (LinkedIn messaging is on
its list of messaging sites). The ritual itself sends nothing.

## What the list does not give

- **The minute.** Today's entries carry a clock time; older ones carry only the day. `--since` is a day, and a
  read overlaps the last one by a day on purpose.
- **A thread id.** List entries carry no link. A conversation is known by its participants' names, and the
  watermark is per inbox, not per conversation.
- **Everything at once.** The list is virtual: only what has been scrolled into view is in the text.
- **A filtered view.** The buttons above the list (Jobs, Unread, Connections, InMail, Starred) narrow an inbox;
  they are not inboxes, and the read presses none of them. InMail arrives in the focused or the other list.
- **Archived and Spam.** Both sit in the same menu as the other inbox; neither is read.
- **Page inboxes.** A page the account administers has an inbox of its own, listed beside the conversation list.
  None is read.

## Messenger's chat list

Messenger runs inside facebook.com, and it reaches a mailbox only as notification emails that hide most of what was
said. Its chat list shows what a ritual needs without opening anything: who, the age of the last message, who spoke
last (`You: `), the last message, an unread mark and Messenger's own `Follow up?` nudge. `messenger_messages.py`
prints a read-only extractor for the list, reads what it saved and states how far back the read went.

### The declaration

```yaml
# .agents/messenger-sync.yaml
workspace: personal
inboxes: [chats, requests, archived]   # the inboxes to read; all three when left out
```

### Never open a chat in the daily read

Every inbox is read at `https://www.facebook.com/messages/t/`, which shows the list beside "No chats selected" and
opens no chat. A chat's own address (`/messages/e2ee/t/<digits>/` for an end-to-end encrypted chat, `/messages/t/<id>/`
for a plain one) opens it, and so does a click on its row. Opening a chat marks it read in the principal's view; with
their read receipts off the other person is not told, but the principal loses the unread mark that would have shown
them it waits. If the page was a chat's address when the extractor ran, `parse` counts that chat as opened and names
it, and the plan says so.

### The three inboxes

- **chats** is the All tab's grid, labeled `Chats`. The Unread, Groups and Communities tabs narrow it; they are not
  inboxes, and the read presses none of them.
- **requests** is Message requests, where messages from people the account is not connected to wait. The menu button
  `Settings, help and more` (in the `Thread list` navigation) opens `Inbox settings menu`; its `Message requests` item
  opens a panel at the same address holding the grid `Requests`, on its `You may know` tab. The `Spam` tab is not read.
- **archived** is Archived chats, from the same menu: a panel holding the grid `Archived chats`. An empty one says
  `No archived chats`.

The two panels have no address of their own, so reading them takes two clicks on the menu. Give each click a summary
that says what it opens ("Opens the inbox settings menu", "Opens the message requests list"): the browser guard holds a
click with no summary on a messaging page. A panel left behind keeps its rows with empty text, so the extractor reads
only the grid named for the inbox being read, and a row with no text is never counted as read.

### The read

1. `python3 <rituals>/scripts/messenger_messages.py plan --config .agents/messenger-sync.yaml` prints, per inbox, what
   to open and the day to scroll back to: the day the last read reached, or two weeks back for a first read.

   ```text
   open  https://www.facebook.com/messages/t/  (chats: the chat list beside "No chats selected"; never a chat's own address, which opens the chat and marks it read)
   read  chats: read through 2026-11-13; scroll back to that day, stop there, and pass --inbox chats --since 2026-11-13
   open  https://www.facebook.com/messages/t/  (requests: then Settings, help and more > Message requests; read the grid named Requests, ...)
   read  requests: never read; scroll back to 2026-10-31, stop there, and pass --inbox requests --since 2026-10-31
   ```

   Steps 2 to 5 are done once for each inbox, with its own day and its own watermark target.
2. Open the address in the browser profile where the principal is signed in to Facebook, and for requests or archived
   open the panel from the menu. Scroll the list (not the page) one screen at a time and look at the oldest row's age
   after each step. A row shows an age, never a date, and the day it stands for is the latest that age allows: on
   2026-11-14 a row showing `2w` stands for 2026-10-31, and a `Follow up?` row, which shows no age, for no day. **Stop
   as soon as the oldest age reaches the day `plan` named.** The list loads more rows for as long as it is scrolled.
   Click no row.
3. `python3 <rituals>/scripts/messenger_messages.py extractor --inbox <inbox>` prints the script. Run it with the
   browser's JavaScript tool and save what the tool returns, as it returns it, to a file; note the time of the read.
   It reads the grid's rows (their text lines, links and labels), the page's address, any dialog over the list and,
   when the grid is missing or empty, the page's text. It clicks, types, scrolls and sends nothing, so the browser
   guard lets it through as a read.
4. `python3 <rituals>/scripts/messenger_messages.py parse --text <file> --read-at <ISO time> --inbox <inbox> --since
   <day>` prints the coverage line, then a chat open during the read, then each chat that ends with someone else, then
   each chat Messenger nudges:

   ```text
   Messenger, chats: 6 conversations read from the list, back to 2026-10-31; 4 end with someone else (2 unread); Messenger suggests a follow-up on 1; none opened
     2026-11-14 (2h) Bo Becker: Are you around next week? I have a question about the board deck.  [unread]
     2026-11-10 (4d) Cy Castillo: Cy sent a photo.
     follow up? Dee Dunn: You: Thanks, talk soon.  [Messenger suggests a follow-up]
   ```

   Exit 0: the read is complete. Exit 1: it stopped short of `--since`, no row it read shows an age, or a row could
   not be read; scroll further or look at the row, and read again. Exit 2: the saved text is not the extractor's, the
   read is of another inbox's grid or holds no grid of this one, or the page shows a sign-in page, a security check or
   a PIN prompt. **At a sign-in page, a security check, a PIN prompt or any warning from Facebook, stop and tell the
   principal.** An empty inbox is a complete read only with `--empty`, and only where the grid is on the page or the
   panel says it is empty (`No archived chats`). A short list whose oldest row is newer than `--since` (two message
   requests, say) is a complete read only with `--end`: scroll to its bottom, wait, see that nothing more loads, read,
   and pass the flag; it is refused unless the extractor saw the list at its bottom. The extractor looks for the list's
   scroll containers from its first row up (on facebook.com one sits inside the grid) and reports the list at its
   bottom only when it finds one and each is at its end. `--json` gives every chat (`who`,
   `chat`, `age`, `last`, `from_me`, `kind`, `unread`, `nudge`, `active`, `open`, `preview`), the owed and nudged chats
   and the coverage (`threads`, `oldest`, `since`, `opened`, `unreadable`, `complete`, `through`).
5. Record the read: `python3 <rituals>/scripts/sync_watermark.py advance --workspace <W> --surface messenger --target
   <inbox> --through <read time> --coverage <the --json output>`. The watermark moves only with a complete read's
   coverage, as LinkedIn's does.
6. The coverage line goes in the plan's sync state, word for word. It names no one.

### What is owed

- The candidates are the chats that end with someone else. A thank-you or a reaction to the principal's own message is
  closed; anything that asks, offers or invites goes to the plan with its age and its preview.
- An unread mark, a message request and `Active now` are reasons to look, not verdicts.
- Messenger's `Follow up?` sits on a chat that ends with the principal: the other person has not answered. List it for
  the principal to weigh; nothing is owed by the principal there.
- A preview that cannot show whether something is owed goes to the plan as it is, for the principal to open. The daily
  read opens no chat.

A reply is a send like any other: it goes through the correspondence skill, and the send guard holds it for the
principal's code (Messenger is on its list of messaging sites). The ritual itself sends nothing.

### What the list does not give

- **A date.** Ages run in minutes, hours, days and weeks (a `y` age is read as at least that many 365-day years); each
  stands for the latest day it allows, so the coverage never claims a day the read did not see.
- **The whole conversation.** A row carries one preview, which may be cut.
- **Everything at once.** Rows load as the list scrolls; only what was scrolled into view is in the read.
- **The Spam tab of message requests, and communities.** Neither is read.
- **A chat's text.** When an export lacks a chat's text, `synthesis-message-exports` saves it from the chat's page
  (`chat_page.py`), on the principal's word for that chat, since reading it opens the chat.
