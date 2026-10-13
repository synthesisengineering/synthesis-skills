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

The example dates and identity are synthetic. The operator supplies actual
scope; no default personal path exists. Windows are half-open, timezone-aware,
and at most 366 days. Pages contain at most 100 examined message rows.
The reader starts at zero and keeps its cursor in the state directory; the
request carries no cursor. A different request, or a replaced database file,
needs its own state directory.

Supported shapes are explicit schema contracts, not universal app-version
claims:

- `imessage-v1`: `message`, `handle`, `chat`, `chat_message_join`,
  `chat_handle_join`, `attachment`, and `message_attachment_join`; message
  dates are nanoseconds since 2001-01-01 UTC.
  Required columns are listed in `SCHEMAS` in the reader. Ambiguous chat joins
  refuse attribution. Message GUID plus database, row, and chat identify a
  pointer; an app URL is not invented.
- `whatsapp-v1`: `ZWAMESSAGE` and `ZWACHATSESSION`, with the exact required
  columns in `SCHEMAS`; dates are seconds since the same epoch. Session type
  zero means direct and one means group in this named contract. Other shapes
  and enum values are unavailable until independently qualified.

An iMessage row names its chat through one `chat_message_join` row. An outgoing
row (`is_from_me` 1) that has a handle but no join is attributed to that
handle's one-to-one chat, the chat whose only `chat_handle_join` member is that
handle, when exactly one exists: an outgoing row's handle is its recipient.
Excluded chats, the window and every skip rule then apply to it as to any
message in that chat, and `coverage.by_handle` lists its row. With no such chat
or several, the row stays a gap whose reason gives the count. An incoming row's
handle is its sender, who may write in any chat, so an unjoined incoming row
stays a gap, as does a row with several joins.

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
the cursor passed.

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
truncated. No database-wide hashing or copying is performed.

## State and output

Output is a bounded page of candidate notes and pointers plus examined range,
skip counts, gaps and the sandbox used, with the rows that are `marked`,
attributed `by_handle` or `reviewed`. Candidate categories
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
unsynced messages, unsupported schemas, structured group mentions, or a whole
conversation's meaning. Those limits remain visible in review coverage.
