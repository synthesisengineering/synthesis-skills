# Adapter and coverage contract

Read before invoking the reader, `scripts/local_messaging.py`. Its request
file holds exactly these fields:

```json
{
  "schema": 1,
  "adapter": "imessage-v1",
  "database": "/absolute/authorized/database.sqlite",
  "start": "2001-01-01T00:00:00Z",
  "end": "2001-01-31T00:00:00Z",
  "page_size": 100,
  "excluded_chats": [],
  "self_names": ["Sample User"]
}
```

One optional field, `"watched_chats": ["<chat identifier>", ...]`, names chats
to read whole: a group the principal asked to monitor (2026-10-20, a trip's SMS
group) keeps every message as a note of class `watched`, where an unwatched group
keeps only messages naming a self name. Likely verification codes are still
skipped, and a chat cannot be both watched and excluded. A request with the field
is a different request, so it needs its own state directory.

The example dates and identity are synthetic. The operator supplies actual
scope; no default personal path exists. Windows are half-open, timezone-aware,
and at most 366 days. Pages contain at most 100 examined message rows.
The reader starts at zero and keeps its cursor in the state directory; the
request carries no cursor. A different request, or a replaced database file,
needs its own state directory. The stale threshold is a command-line option,
`--stale-after-hours` (see [Stale stores](#stale-stores)), so it can change
between runs of one window.

Supported shapes are explicit schema contracts, not universal app-version
claims:

- `imessage-v1`: `message`, `handle`, `chat`, `chat_message_join`,
  `chat_handle_join`, `attachment`, and `message_attachment_join`; message
  dates are nanoseconds since 2001-01-01 UTC. `chat_recoverable_message_join`,
  where Messages' Recently Deleted (macOS 13 and later) keeps a deleted
  message's chat, is read when present and needs `chat_id` and `message_id`.
  Required columns are listed in `SCHEMAS` and `OPTIONAL` in the reader.
  Ambiguous chat joins refuse attribution. Message GUID plus database, row, and
  chat identify a pointer; an app URL is not invented.
- `whatsapp-v1`: `ZWAMESSAGE` and `ZWACHATSESSION`, with the exact required
  columns in `SCHEMAS`; dates are seconds since the same epoch. Session type
  zero means direct and one means group in this named contract. Other shapes
  and enum values are unavailable until independently qualified.

An iMessage row names its chat through one `chat_message_join` row. When the
principal deletes a message, Messages moves that link to
`chat_recoverable_message_join` (Recently Deleted, kept about 30 days), so the
row has no `chat_message_join` row. A row with exactly one such record takes
the chat it names: an excluded chat skips it as `excluded-chat`, and otherwise
it is skipped as `deleted`, its body never read, because a message the principal
deleted is not a candidate. Both field reports of unjoined rows were this shape:
on 2026-10-08 seven outgoing rows, on 2026-10-19 five incoming rows, each from a
handle that belongs to exactly one chat, a one-to-one chat (two iMessage, three
SMS), and that chat was the one each record named.

No chat is inferred from a handle. Until 2026-10-20 an unjoined outgoing row
took its recipient handle's one one-to-one chat; a store can file a message to a
handle in another one-to-one chat than the one that handle belongs to, so that
was a guess. Every other row without a single chat stays a gap whose reason says
why: `N chat links`, `no chat link and no (or N) Recently Deleted records`,
`no chat link` (a store without that table, or a WhatsApp row without a chat
session), `its chat has no identifier`, or `chat membership unknown` (a chat
listing no members, or a WhatsApp session type other than 0 or 1).

Plain text is bounded at 256 KiB. A restricted binary NSKeyedArchiver plist
can supply `NSString` or `NS.string` through bounded UID references. The reader
checks the binary object count before parsing, rejects cycles and unsupported
structures, and never instantiates archived classes. Typedstream, XML archives,
compressed bodies, and attachment extraction are unsupported. A decoding gap
prevents the cursor from advancing.

One case is recorded instead of held. When an iMessage body is in an encoding
the reader does not decode (typedstream, or a keyed archive of another shape)
and the row's own columns show what it is, the row gets a content marker: `[link]`
for a rich link (`balloon_bundle_id` is `com.apple.messages.URLBalloonProvider`),
or `[attachment: image/jpeg]` listing the `mime_type` of each attachment that
`message_attachment_join` names (at most eight; `unknown type` when it is absent
or not a plain MIME type). The marker stands in for the text in the skip rules,
so it never matches a candidate class or a group self name, and
`coverage.marked` lists each such row with its marker. A caption sent with the
link or attachment is not read: open a marked row in the app when it matters.
A row with neither, a broken bound and malformed data still hold the window.

## Closing a gap by hand

A gap holds the window until it is resolved. Excluding the chat resolves it
with a new request and state directory. When the rows have been read in the
app instead, a by-hand review the principal approves closes them. Write the
page's gaps, each row with the reason the page reports, to a file:

```json
{"rows": [{"row": 1234, "reason": "ambiguous chat attribution"}]}
```

and run the same command with `--review REVIEW.json` added. A review must name
exactly the page's gaps; otherwise the reader refuses and prints the gaps the
page holds, and nothing is put to the principal. The first run files a request
with the v5 approvals (`synthesis/approvals.py`) and refuses with a code. Show
the principal the rows and reasons; after they type `approve <code>` in their
own prompt, the identical command closes the gaps. The approval covers
this request, this database file and these exact gaps, is spent once, and
counts only when the harness's record of the session shows the principal
typing it, so an agent cannot close a gap on its own. The saved page lists the
closed rows under `coverage.reviewed` and the cursor moves on. A run stopped
after the approval is spent and before the page is saved asks again. On a page
without gaps the review is not used.

Completeness keeps its meaning: every examined row is a note, a skip by a stated
rule, a marked row, or a row the principal closed by name, recorded in the page
the cursor passed. A page read from a stale store is never complete.

## Stale stores

A reader that checks only what is on disk cannot tell "no new messages" from
"the app stopped syncing". On 2026-10-17 a WhatsApp desktop store stopped
being written, minutes after its newest message; two days later the reader
called the window complete over it, the messages watermark moved past the
stall, and messages that arrived once the app was opened were never read.

So each page also reads, inside the same snapshot, the store's newest message
before the window's reach (its end, or the read time for a window that ends
later) and the modification times of the database file and its `-wal` file. A
store with no write and no message for longer than the threshold before that
reach is stale. The threshold is `--stale-after-hours`, by default 12 for
WhatsApp and 24 for iMessage: in 90 days of the principal's stores, WhatsApp never
went 12 hours without a message, while iMessage did 27 times but never 24. So a
quiet night is not a stopped store, and a store that stopped syncing is caught by
the next day's first read. Raise it for an account that often stays silent
longer; lower it for a busy one. A store last written after the window ends is never stale.

WhatsApp syncs only while it runs, and quitting it can write the store hours after
its newest message, so the file times alone can make a quit app look current. When
the WhatsApp app is not running (the coordinator asks `pgrep`, outside the sandbox,
and a failed check counts as not running), its page is stale whatever the
threshold says (2026-10-24: quit with its newest message at 07:26, and a close
moved the watermark to the window's end at 20:45, so the day's messages were read
two days late). iMessage syncs in the background whether Messages is open or not.

A stale page:

- reports `coverage.stale`, a sentence giving the hours, the newest message and
  both file times, and is never `complete`;
- sets `coverage.through` to the store's newest message (the window start when
  that message is older), the furthest a sync watermark may move, never the
  window end;
- is saved with its notes, but its cursor stays open and drops the snapshot
  bound, so the next run takes a new snapshot and reads the rows the app syncs
  later (their row ids are higher; their dates may fall anywhere in the window).

Ask the principal to open the app and let it sync, then run the same command
again; once the store has been written within the threshold the window can
complete. When the principal confirms a store is current and simply quiet, a
larger `--stale-after-hours` on the same state directory completes it. A
daily ritual moves the app's watermark to `coverage.through` and defers the
target with the `coverage.stale` reason while the store is stale. If
`coverage.through` is earlier than the watermark already recorded, an earlier
read moved past messages the store did not yet hold: once the app has synced,
read again from `coverage.through` in a new window.

`coverage.store` carries the facts behind the decision: `newest_message`,
`database_modified`, `wal_modified` (null without a `-wal` file),
`stale_after_hours` and `reach`, the moment `through` takes once the window is
read with no gap. `through` is null while a gap holds the page or pages remain.

## The sandbox and SQLite

The reader copies itself and the page request into a fresh temporary folder and
runs there under the OS sandbox in `scripts/os_sandbox.py`: macOS
`sandbox-exec` or Linux bubblewrap (`bwrap`), with the database's folder
read-only, only the temporary folder writable, no network, and a 15-second
limit. Without a working sandbox it refuses; there is no unsandboxed fallback.
The worker observes denied write-open on the main file and existing sidecars
before opening SQLite with `mode=ro`.
SQLite query-only mode is additional protection, not the confinement boundary.
There is no immutable URI, backup, permission change, hidden copy, network
access, or account discovery fallback.

SQLite documents [read-only WAL access](https://sqlite.org/wal.html#read_only_databases)
with readable existing WAL/SHM files. Its [immutable URI option](https://sqlite.org/uri.html)
asserts that a database cannot change and skips locking/change detection; it
is unsuitable for a live app database. Missing readable sidecars or unavailable
OS isolation produces an explicit refusal. Platform and interpreter versions
must be qualified in the actual installation.

Each page has one SQLite read transaction and finite query/process limits.
The first page fixes the upper row bound of the window's snapshot; later pages
read up to that bound, so messages arriving during a long read do not move the
target. A database whose highest row falls below that bound refuses as
truncated. A page read from a stale store does not keep the bound: the next run
takes a new snapshot. No database-wide hashing or copying is performed.

## State and output

Output is a bounded page of candidate notes and pointers plus examined range,
skip counts, gaps and the sandbox used, with the rows that are `marked` or
`reviewed`, the store's freshness (`stale`, `store`) and `through`. Candidate categories
are heuristic. No raw message body or media bytes enter the result. Exclusion
and window tests precede logical body fetch/decoding; SQLite may read storage
pages containing neighboring data internally.

The state directory is created with mode 0700 and an exclusive lock prevents
two readers of one window at once. It holds `cursor.json` (bound to the request
and the database file's identity) and one `page-<after>-<through>.json` per
page. Each page is saved before the cursor moves, so a crash between the two
reads the same page again and loses no notes. A finished window replays its
last page without another read. The reader refuses a state directory holding
files it did not write, and never adopts or cleans one.

This scan cannot reconstruct deletions, edits between historical generations,
unsynced messages (a stale store is reported, never filled in), unsupported
schemas, structured group mentions, or a whole conversation's meaning. Those
limits remain visible in review coverage.
