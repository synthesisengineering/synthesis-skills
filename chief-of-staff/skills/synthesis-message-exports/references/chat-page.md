# One chat read from its page, when an export lacks it

Meta's downloads can leave a chat's text out: the secure-storage download of 2026-11-14 held a file for most encrypted
chats with no message in it, and exports have dropped whole threads. `scripts/chat_page.py` saves one chat's text from
its page on facebook.com into the same transcripts the importer writes, so a later export of that chat adds only what
the transcript lacks. Read this before reading a chat's page.

Contents:
- When to use it, and what it costs
- The read
- What `save` prints
- How its messages pair with an export's
- Where the messages go
- What the page does not give

## When to use it, and what it costs

Only for a chat the principal names, an export lacks, and they ask to have saved (SKILL.md, rule 1). **Opening a chat
marks it read in the principal's view.** With their read receipts off the other person is not told, but the chat's
unread mark is gone, so a message the principal had not seen is now shown as read: say so before opening it. The daily
rituals never open a chat; this fallback does, once, on the principal's word.

## The read

1. Open the chat in the browser profile where the principal is signed in: its address is
   `https://www.facebook.com/messages/e2ee/t/<digits>/` for an end-to-end encrypted chat and
   `https://www.facebook.com/messages/t/<id>/` for a plain one (or the same on messenger.com).
2. Scroll the message log up until messages from before the day asked for show; older messages load as the log scrolls
   up.
3. `python3 scripts/chat_page.py extractor` prints the script. Run it with the browser's JavaScript tool and save what
   the tool returns, as it returns it, to a file in the private folder or the session's scratch folder, never in a
   repository: it holds whole messages. The script reads the log labeled `Messages in conversation with <Name>`: for
   each message, the labels of its article (`Enter, Message sent <date>, <time> by <Sender>: <text>` and
   `At <date>, <time>, <Sender>: <text>`), and for any other item its text; the page's address, clock and time zone;
   and each dialog's heading, never its text. It clicks, types, scrolls and sends nothing, so the browser guard lets it
   through as a read.
4. If the log drops what it scrolled past, run the extractor at each screen, each read overlapping the one before by
   two messages or more, and pass them all to one `save`. Reads that share fewer than two messages are not one read:
   the coverage stops where they meet, and a single message they share may be two identical messages from one minute,
   so it is written once and held for a person.
5. `python3 scripts/chat_page.py save READ [READ ...] --out PRIVATE_FOLDER --since YYYY-MM-DD --principal "NAME"`,
   with `--dry-run` first to see what it would write. `--since` is the day asked for, a real day. `--principal` is the
   principal's name exactly as the export writes it (any transcript's `Participants:` line shows it); the page calls
   them `You`, and a read that holds their messages is refused without it. `--into FILE` names the transcript to extend
   when none holds this chat yet (below).

Exit 0: saved, the day asked for reached, nothing held. Exit 1: saved, but short of that day, or with messages it could
not read or held for a person; scroll further up, read again and save again, which adds only what is new. Exit 2:
refused, nothing written: a `--since` that is no day, a file that is not the extractor's, a sign-in page, a security
check or a PIN prompt (**stop and tell the principal**), a page that is no chat's own address, a time zone this Python
does not know, reads of two chats, two transcripts that hold this chat, or an `--into` transcript that is another
conversation's.

## What `save` prints

```text
page read: 4 messages from 1 read, back to 2024-03-05 09:02 America/New_York; it reaches 2024-03-06, the day asked for; 1 notice not written
transcript: messenger-e2ee-Alex-Sample-3f9a2c1d.md (new): 4 new, 0 already in it
```

The first line is the coverage: how many messages the reads held, the oldest local time they cover without a gap from
the newest read, and whether that reaches the day asked for. **A day is reached only when a message from before it was
read**: a read whose oldest message is that day's evening says `it stops short of <day>, the day asked for: scroll the
log further up and read again`. It adds where reads do not overlap by two messages, `N could not be read` for a message
whose labels are in no known shape or disagree, `N held for a person (...)` for what may be a message but cannot be
written safely (below), and `N notices and N without text not written`. The notice is the item where a chat became end-to-end
encrypted: it carries a message's label, sent at time zero in the browser's zone (in New York, December 31, 1969, 7:00
PM) by `a participant`, and stands where the chat became encrypted, not at its start; it is never written and reaches
no day. `not joined: <file>: <why>` names a transcript that held one of the read's messages but is not this chat's. The
last line names the transcript, `new`, `extended` or `unchanged`, and the counts. No line carries message text.

Held for a person, never written and never dropped:

- a message whose label is dated before 2004-02-04, which carries no date;
- an item whose labels match no message (the encryption notice is the only labeled item that is no message);
- a possible twin where two reads meet at a single message;
- a message like one already in the transcript in its minute, with other words or another sender: perhaps the same
  message edited, quoted in a reply or credited otherwise, so neither copy wins on its own.

## How its messages pair with an export's

A message read from the page is written exactly as the importer writes one (references/transcript-format.md), keyed
by the importer's scheme: `<time in milliseconds>-<10 hex digits>`, the digits from the same digest of what it says.
The page shows only the minute, in the browser's time zone, so its time is that minute in UTC, and its block carries
one more line, third, before its text:

```text
**Read from the page:** `https://www.facebook.com/messages/e2ee/t/1234567890/`, to the minute
```

**A message pairs on its sender, its minute and a digest of its text alone.** A later import of the same chat counts
an export message as already in the transcript when a page block has its sender, its text and a minute holding its
time; a page read after an export pairs with the export's blocks the same way. A link the export carries beside the
text, or an attachment's name, takes no part, so a message with a link pairs too. Each block pairs with one message, so
two people's `ok` in one minute stay two, each with its own. In the hour the clocks went back each local time happens
twice and the page cannot say which: the first is written, and the line adds `; the clocks went back that hour, so it
may be 60 minutes later`, which the pairing reads. A message that pairs only in part is held for a person (above), in
the import as in `save`: the import prints `held for a person: <file>: <N> messages like one read from the page in its
minute ...` and exits 1.

## Where the messages go

1. The transcript holding this chat's earlier page reads (by the address in that line), so a read that holds none of
   the messages written before still lands beside them.
2. Else a transcript holding any of its messages, **on evidence about the chat itself**: it names the person or title
   the log names (in its title, participants or senders), and every message of it inside the read's span pairs with
   one read. A coincidence (the same greeting in two groups of the same people, the principal's `ok` to two people in
   one minute) never joins two chats: the transcript passed over is named, and the read starts or keeps its own.
3. Else the transcript `--into` names, on the same evidence. Use it to extend an export's transcript the read does not
   overlap; reading back to a day that transcript already holds does the same.
4. Else a new transcript, named as the importer names a secure-storage conversation (`messenger-e2ee-<name>-<8 hex>.md`,
   the hex from the first message's ID) for an encrypted chat, or `messenger-page-<name>-<8 hex>.md` for a plain chat,
   whose regular-export folder name the page does not show. Its header says `(page read)` and names the page.

The importer, for its part, takes a conversation of either download into a transcript holding its page-read messages on
the same evidence: that transcript's title is among the conversation's people or its title, and every page-read block
inside the conversation's span pairs. Where the conversation also has a transcript of its own (its folder's, or the one
holding its messages by ID), the page-read transcript keeps what it holds, the rest goes to the conversation's own, and
the import says so (`split: <file>: N of its messages are held from a page read in <file>`); it is never skipped for it.
The importer keeps the five header lines of a transcript a page read started; extending any transcript, `save` keeps
its header as it was.

## What the page does not give

- **The second, or the time of a message with no text.** Photos, stickers and other media are counted, not written.
- **The other person's view.** Reactions, edits and replies show as the page labels them, and only the label's text is
  written; a message whose label carries other words than the export's text is held when the export brings it.
- **The chat's beginning.** The encryption notice stands where the chat became encrypted, not at its start (in the
  first live read, between messages of 2024 and 2025), so the coverage rests on the oldest message read and never
  claims the start.
- **A sender's name with `: ` in it, in a group.** The sender ends at the name the log gives, or `You`, where the label
  carries it; else at the first `: `.
