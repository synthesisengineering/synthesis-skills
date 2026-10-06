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

- `imessage-v1`: `message`, `handle`, `chat`, `chat_message_join`, and
  `chat_handle_join`; message dates are nanoseconds since 2001-01-01 UTC.
  Required columns are listed in `SCHEMAS` in the reader. Ambiguous chat joins
  refuse attribution. Message GUID plus database, row, and chat identify a
  pointer; an app URL is not invented.
- `whatsapp-v1`: `ZWAMESSAGE` and `ZWACHATSESSION`, with the exact required
  columns in `SCHEMAS`; dates are seconds since the same epoch. Session type
  zero means direct and one means group in this named contract. Other shapes
  and enum values are unavailable until independently qualified.

Plain text is bounded at 256 KiB. A restricted binary NSKeyedArchiver plist
can supply `NSString` or `NS.string` through bounded UID references. The reader
checks the binary object count before parsing, rejects cycles and unsupported
structures, and never instantiates archived classes. Typedstream, XML archives,
compressed bodies, and attachment extraction are unsupported. A decoding gap
prevents the cursor from advancing.

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
skip counts, gaps and the sandbox used. Candidate categories
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
