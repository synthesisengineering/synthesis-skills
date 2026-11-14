# The formats the importer reads

What each export looks like, which field becomes what in a transcript, how text is repaired, and how sure each fact
is. Read it before running the importer on a new export, and whenever it refuses one.

Contents:
- How sure each fact is
- What Meta documents
- The regular export of Messages in JSON: layouts, sections, files, media
- Its fields, and how each is shown
- The encoding quirk and its repair
- The secure-storage download of end-to-end encrypted chats
- What the importer refuses, and why
- Not established
- Sources

## How sure each fact is

- **Confirmed:** Meta says so on its own pages, or a real download showed it (file names, keys and sizes, read by
  the session that requested the download; this skill's authors never see a real export).
- **Corroborated:** two or more independent sources agree, none of them Meta.
- **Inferred:** one source, or a reading of the evidence. The importer treats an inferred fact as a check to
  make, not a promise: anything that does not match is refused (see "What the importer refuses").

Meta publishes no schema for either download; the field names come from real exports and from open-source tools
that read them [S7]. Bracketed tags refer to "Sources" at the end.

## What Meta documents

- **Confirmed.** "Download your information" (also shown as "Export your information") makes a ZIP of the
  information chosen, for a date range, in HTML (to read in a browser) or JSON ("a machine readable format"), with
  a choice of media quality [S1]. The importer reads only JSON; an HTML export is refused (see below).
- **Confirmed.** Messenger's personal chats became end-to-end encrypted by default from December 2023, rolling out
  over the following months; their history is kept by "secure storage", opened with a PIN or a stored key [S3].
- **Confirmed.** A person "can download a copy of" their end-to-end encrypted chat history at any time [S2]. Meta's
  page names no format.

## The regular export of Messages in JSON

### Where the messages folder sits

| Exports from | Messages folder | How sure |
|---|---|---|
| before 2024 | `messages/` at the top | Corroborated [S6, S10] |
| 2024 | `your_activity_across_facebook/messages/` | Inferred [S6] |
| 2025 on | `your_facebook_activity/messages/` | Corroborated [S6, S7, S8] |

The importer finds the messages folder at the top of the export, under one folder the export was extracted into
(`facebook-<name>-<date>-<id>/`), or under either activity folder with or without that outer folder. A folder
given as the export that is itself named `messages` is read as the messages folder. Another product's activity
folder (`your_instagram_activity`) is not read as Messenger's.

### Sections

Under the messages folder, one folder per section, each holding one folder per conversation. Corroborated [S6, S8]:

| Section | What it holds |
|---|---|
| `inbox` | conversations in the inbox |
| `archived_threads` | conversations the person archived |
| `filtered_threads` | conversations Messenger filtered out of the inbox (spam) |
| `message_requests` | messages from people not yet accepted |
| `e2ee_cutover` | the part of each chat from before it switched to end-to-end encryption; the rest comes in the secure-storage download (corroborated [S5, S7]) |

A conversation found in two sections is one conversation, and its transcript names both.

### Files

- Each conversation folder holds `message_1.json`, `message_2.json` and so on: one thread split into files of at
  most 10,000 messages each. Corroborated [S8, S9].
- Within a file the messages are listed newest first. Inferred [S9]. The importer orders every conversation by
  time, so which file holds which stretch does not matter; messages of the same moment keep the export's order.
- A conversation's folder name, such as `alexsample_1234567890`, is the conversation's id in the export, and the
  importer names the transcript by it. Whether Meta keeps a folder's name when a group is renamed is not
  established.
- Attachments sit in folders inside the conversation's folder (`photos/`, `videos/`, `audio/`, `files/`, `gifs/`);
  stickers in `stickers_used/` beside the sections. Corroborated [S8, S10]. In exports of about 2020 a
  conversation's media had a folder of its own, its name in mixed case beside the lowercase one [S10]; the
  importer counts it as media, since it holds no message file.
- A large export comes as several ZIPs. One part can hold only media and no JSON, and each part can carry an empty
  stub ZIP at its top. Corroborated as observed in one real export [S8]. Run the importer on each part with the
  same `--out`; a part with only media reports no conversations and writes nothing.
- Before 2018 messages came as one HTML file, `messages.htm` [S12]; the importer does not read it.

## Its fields, and how each is shown

Thread level (corroborated [S6, S8]): `participants`, a list of objects with `name`; `title`, the group's name or
the other person's; `messages`, the list below; and keys the transcript does not show, such as `thread_type` and
`thread_path`.

| Message field | What it holds | How sure | In the transcript |
|---|---|---|---|
| `sender_name` | who sent it | Corroborated [S6, S7, S8, S9] | the message heading |
| `timestamp_ms` | when, in milliseconds since 1970 (UTC) | Corroborated [S6, S7, S8, S9] | the heading's time, its day heading, its Message ID |
| `content` | the text | Corroborated [S6, S7, S8, S9] | a fenced block marked `untrusted` |
| `photos`, `videos`, `audio_files`, `files`, `gifs` | lists of objects with `uri` (and `creation_timestamp`) | Corroborated [S6, S8] | counted by kind, each `uri` listed in a fenced block; never copied |
| `sticker` | one object with `uri` | Corroborated [S6, S8] | listed as a sticker |
| `share` | an object with `link` and `share_text` | Corroborated [S6, S8] | "Shared link", fenced |
| `reactions` | a list of objects with `reaction` and `actor` | Corroborated [S6, S8] | "Reactions", each emoji and who |
| `call_duration` | a call's length in seconds | Corroborated [S6, S8] | "Call", as hours, minutes and seconds |
| `missed` | a missed call | Inferred [S6] | "Call: missed" |
| `is_unsent` | the sender unsent it | Inferred [S7] | "Unsent by its sender." |
| `type` | a message's kind | Inferred [S6] | not shown; the other fields say it |

A message must have a whole-number `timestamp_ms`; a field the table lists must have the shape it gives; otherwise
the export is refused. Any other message field is counted by name under "fields not shown", so a field Meta adds
is reported rather than passed over.

Messages carry no id of their own [S7]. The importer names each by its time and a digest of what it says (sender,
text, attachments, link, call, unsent), so a later export of the same conversation names each message the same
way whatever it gained since, such as a reaction. A message repeated within one file keeps each copy; one repeated
across files of a conversation is one message.

## The encoding quirk and its repair

The regular export writes non-ASCII text one UTF-8 byte at a time, each byte as its own `\u00XX` escape, so a
standard JSON reader returns each byte as a Latin-1 character: `CafÃ©` reads as "CafÃ©", and an emoji
as four odd characters. Corroborated [S6, S7, S11].

The repair encodes the text as Latin-1 and decodes the bytes as UTF-8 [S7, S11]. The importer applies it to every
string it shows (text, names, titles, links, attachment names, reactions) only where it round-trips: every
character fits Latin-1 and the bytes then form valid UTF-8. Text that is already right is left as it is, because it
fails one test or the other: "Café" written correctly is the byte E9 alone, which is no UTF-8, and "Přeji" holds a
character beyond Latin-1. The repair is applied once, never twice, so text whose author typed "Ã©" keeps it.

## The secure-storage download of end-to-end encrypted chats

Prepared in the browser on a computer, at `facebook.com/secure_storage/dyi` [O1], reached from Messenger's
settings (Privacy & safety, End-to-end encrypted chats, Message storage, "Download secure storage data"), as one
ZIP of JSON files [S4]; the help pages say only that the download exists [S2]. It holds the chats from the start of the account's secure storage, so the same person's
older history comes from the regular export.

The layout of a real download, observed on 2026-11-14 (confirmed, one download [O1]):

- One JSON file per conversation at the ZIP's top level, named `<thread display name>_<n>.json`, with `n` a
  running index across the download. Display names repeat across conversations, so the file name as a whole is the
  conversation's id.
- `media/<uuid>.jpeg` beside them: the attachments, which the importer names and never opens.
- Each file is one object: `{"participants": [text], "threadName": text, "messages": [{"isUnsent": bool, "media":
  [], "reactions": [], "senderName": text, "text": text, "timestamp": whole number, "type": text}]}`. The keys are
  camelCase, unlike the regular export's.
- Most files hold no messages. An empty conversation is counted under "with no messages" and gets no transcript.

Two open-source importers read the same keys (corroborated [S6, S7]); they find the files in
`your_activity_across_facebook/messages/` rather than at the top, so the importer reads either place.

What is not established, and how the importer handles it:

- **The timestamp's unit.** Both importers read milliseconds [S6, S7]; the real download did not settle it. The
  importer decides per file by size: every timestamp under 10^11 counts seconds (10^11 milliseconds is 1973,
  10^11 seconds the year 5138), every one at or above it milliseconds, and a file with both is refused. A
  converted time before 2004 or after the present is refused too.
- **The encoding quirk.** Whether this download carries it is unknown. Both importers repair its text [S6, S7];
  the importer applies the same repair, only where it round-trips.
- **An attachment's shape.** The real download showed the key, not its elements. One importer reads objects with a
  `uri` such as `./media/<uuid>.jpeg` [S6]. The importer takes an object with a text `uri`, or the text itself, and
  names its kind by extension (photo, gif, video, audio file, otherwise file); anything else is refused.
- **Whether `n` stays with its conversation** from one download to the next. So a secure-storage transcript is
  extended only when the export lists exactly the participants the transcript recorded; otherwise that
  conversation is skipped and named, and two conversations are never mixed.

Transcripts from the two downloads never collide: regular-export transcripts are named `messenger-dyi-<id>.md`,
secure-storage transcripts `messenger-e2ee-<id>.md`, and each records its source.

## What the importer refuses, and why

Every refusal exits 2 and writes nothing. A refusal for a shape it does not know lists the export's files by name
and size (media counted by extension, not listed), never their contents.

| It refuses | Why |
|---|---|
| a file in a messages folder in a place or shape this reference does not describe (an HTML thread, `message_final.json`, a thread without `participants` or `messages`, a message without its time) | partly reading a changed format would look complete and not be |
| an export with no messages folder and no conversation file | it is not an export this importer knows |
| a ZIP entry whose name could lead outside the archive (`..`, a leading `/`, a drive letter, a backslash, a control character), a link entry, or a name given twice | an archive that could write or hide outside itself is not Meta's |
| a message file over 256 MiB (one holds at most 10,000 messages); media is never opened, whatever its size | a bound on what one read takes |
| a link inside an export folder, or something that is not a file | a link could lead the reader outside the export |
| `--out` inside the export, or the export inside `--out` | reads and writes stay apart |
| two conversations whose file names are the same or differ only in case | a Mac's disk would give them one file |

## Not established

- The format's history before about 2018, and whether a single unnumbered `message.json` ever named a thread file;
  the importer refuses one rather than guess.
- Whether a renamed group keeps its folder name in the regular export, and whether the secure-storage index `n`
  stays with its conversation across downloads (handled as above).
- The secure-storage download's timestamp unit, its encoding, and its attachment elements (handled as above).
- Whether any export keeps every thread: one long-standing report found whole threads missing from downloads [S12].
  An export is a bounded source; absence from it proves nothing.

## Sources

Read on 2026-11-14.

| Tag | Source | What it supports | Kind |
|---|---|---|---|
| S1 | https://www.facebook.com/help/212802592074644 | the export's HTML and JSON formats, the ZIP, date range and media quality | Meta's help center |
| S2 | https://www.messenger.com/help/820525008940780/ | a copy of end-to-end encrypted chat history can be downloaded at any time | Meta's help center |
| S3 | https://about.fb.com/news/2024/03/end-to-end-encryption-on-messenger-explained/ | default encryption from December 2023; secure storage | Meta's newsroom, 2024-03-28 |
| S4 | https://deciphertools.com/support/knowledge-base/missing-newer-facebook-messages/ | the secure-storage download's menu path, its JSON files and its ZIP | a vendor's knowledge base |
| S5 | https://redact.dev/blog/download-facebook-data | `e2ee_cutover` holds each chat's part from before the switch | a vendor's guide |
| S6 | https://github.com/kenn-io/msgvault (`internal/fbmessenger/`: `discover.go`, `json_parser.go`, `e2ee_parser.go`) | the three layouts, five sections, field names of both downloads | an open-source importer |
| S7 | https://github.com/NotYuSheng/Doppelganger (`docs/sources/messenger.md`, `ingest/adapters/meta.py`) | two downloads; both shapes and their keys; millisecond timestamps; the repair only where it is valid; no message ids; no published schema | an open-source importer |
| S8 | https://github.com/simontrembler/meta-capsule (`docs/facebook-export-map.md`) | a real multi-part export: media-only parts, stub ZIPs, five sections, 10,000 messages a file, message fields | an open-source project's map of an export |
| S9 | https://alicebarbe.github.io/Pandas-Online-Text-Analysis-Tool/source/chat_format.html | newest first; at most 10,000 messages a file | a tool's documentation (2020) |
| S10 | https://alicebarbe.github.io/Pandas-Online-Text-Analysis-Tool/source/exporting_chats.html | `messages/inbox/<chat>/message_1.json`; a separate media folder | a tool's documentation (2020) |
| S11 | https://sorashi.dev/fix-facebook-json-archive-encoding | the escape quirk and its byte-level repair | a developer's write-up (2019, updated 2022) |
| S12 | https://hackernoon.com/dear-facebook-download-my-archive-is-broken-and-thats-not-okay-a1df2eb9e8a9 | `messages.htm` before JSON; threads missing from downloads | a 2017 account |
| O1 | a secure-storage download observed by the session that requested it, 2026-11-14: file names, keys and sizes only | the layout above | observation |
