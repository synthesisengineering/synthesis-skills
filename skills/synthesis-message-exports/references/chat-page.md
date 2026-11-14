# One chat read from its page, when an export lacks it

Meta's downloads can leave a chat's text out: the secure-storage download of 2026-11-14 held a file for most encrypted
chats with no message in it, and exports have dropped whole threads. `scripts/chat_page.py` saves one chat's text from
its page on facebook.com into the same transcripts the importer writes, so a later export of that chat adds only what
the transcript lacks. Read this before reading a chat's page.

Contents:
- When to use it, and what it costs
- The read
- What `save` prints
- How its messages merge with an export
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
2. Scroll the message log up until the day asked for shows; older messages load as the log scrolls up.
3. `python3 scripts/chat_page.py extractor` prints the script. Run it with the browser's JavaScript tool and save what
   the tool returns, as it returns it, to a file in the private folder or the session's scratch folder, never in a
   repository: it holds whole messages. The script reads the log labeled `Messages in conversation with <Name>`; for
   each message, the labels of its article (`Enter, Message sent <date>, <time> by <Sender>: <text>` and
   `At <date>, <time>, <Sender>: <text>`), and for any other item its text; the page's address; the browser's time zone; and any dialog. It clicks, types, scrolls and sends nothing, so
   the browser guard lets it through as a read.
4. If the log drops what it scrolled past, run the extractor at each screen and save each read; pass them all to one
   `save`, which keeps each message once.
5. `python3 scripts/chat_page.py save READ [READ ...] --out PRIVATE_FOLDER --since YYYY-MM-DD --principal "NAME"`,
   with `--dry-run` first to see what it would write. `--since` is the day asked for. `--principal` is the principal's
   name exactly as the export writes it (any transcript's `Participants:` line shows it); the page calls them `You`, and
   a read that holds their messages is refused without it. `--into FILE` names the transcript to extend when none holds
   this chat yet (below).

Exit 0: saved, and the read reaches the day asked for. Exit 1: saved, but short of that day, or with messages it could
not read or held for a person; scroll further up, read again and save again, which adds only what is new. Exit 2: refused, nothing
written: the file is not the extractor's, the page is a sign-in page, a security check or a PIN prompt (**stop and
tell the principal**), the page is no chat's own address, the read names no time zone this Python knows, the reads
are of two chats, two transcripts hold this chat, or `--into` names a transcript of other people.

## What `save` prints

```text
page read: 4 messages from 1 read, back to 2024-03-05 09:02 America/New_York; it reaches 2024-03-05, the day asked for; 1 notice not written
transcript: messenger-e2ee-Alex-Sample-3f9a2c1d.md (new): 4 new, 0 already in it
```

The first line is the coverage: how many messages the reads held, the oldest one's local time, and whether that reaches
the day asked for (`it stops short of <day>, the day asked for: scroll the log further up and read again` when not). It
adds `N could not be read` for a message whose labels are in no known shape or disagree, and `N notices and N without
text not written` for items that are no message (the encryption notice) and messages with no text on the page (a
photo, a sticker), and `N held for a person` for a message whose label is dated before 2004-02-04, which carries no
date and is never written. The notice where a chat became end-to-end encrypted is one of the notices: it carries a
message's label, sent at time zero in the browser's zone (in New York, December 31, 1969, 7:00 PM) by `a participant`,
and stands where the chat became encrypted, so it is never written and reaches no day. The second line names the transcript, `new`, `extended` or `unchanged`, and the counts. No line
carries message text.

## How its messages merge with an export

A message read from the page is written exactly as the importer writes one (references/transcript-format.md), keyed
by the importer's scheme: `<time in milliseconds>-<10 hex digits>`, the digits from the same digest of what it says.
The page shows only the minute, in the browser's time zone, so its time is that minute in UTC, and its block carries
one more line, third, before its text:

```text
**Read from the page:** `https://www.facebook.com/messages/e2ee/t/1234567890/`, to the minute
```

A later import of the same chat pairs each of its messages with such a block when the digest is the same and the
export's time falls in that minute, and counts it as already in the transcript; each block pairs with one message, so
two `ok`s in one minute stay two. A page read after an export pairs the same way with the export's blocks. Either way
nothing is written twice, and the block written first stays byte for byte. In the hour the clocks went back each local
time happens twice and the page cannot say which: the first is written, and the line adds `; the clocks went back that
hour, so it may be 60 minutes later`, which the pairing reads.

A message pairs only when its text on the page is the text the export holds: a message whose page label carries other
words than its text (a reply, an edit) is written again when the export brings it, as a second block.

## Where the messages go

1. The transcript holding this chat's earlier page reads (by the address in that line), so a read that holds none of
   the messages written before still lands beside them.
2. Else the transcript holding any of its messages, an export's or a page read's, whose people (its participants and
   senders) include every sender of the read: a digest and a minute alone can be the principal's `ok` to two people.
3. Else the transcript `--into` names, when it names every sender of the read. Use it to extend an export's
   transcript the read does not overlap; reading back to a day that transcript already holds does the same.
4. Else a new transcript, named as the importer names a secure-storage conversation (`messenger-e2ee-<name>-<8 hex>.md`,
   the hex from the first message's ID) for an encrypted chat, or `messenger-page-<name>-<8 hex>.md` for a plain chat,
   whose regular-export folder name the page does not show. Its header says `(page read)` and names the page.

The importer, for its part, puts a conversation of either download into a transcript holding its messages read from
the page, with the same people, whatever that transcript is named; a regular-export conversation found both there and
in the transcript named by its folder is skipped and named. Extending a transcript keeps its header's title, source and
participants as they were.

## What the page does not give

- **The second, or the time of a message with no text.** Photos, stickers and other media are counted, not written.
- **The other person's view.** Reactions, edits and replies show as the page labels them, and only the label's text is
  written.
- **The chat's beginning.** The encryption notice stands where the chat became encrypted, not at its start (in the
  first live read, between messages of 2024 and 2025), so the coverage rests on the oldest message's day and never
  claims the start.
