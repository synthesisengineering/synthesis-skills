# Adapter and coverage contract

The CLI accepts a JSON file with exactly these fields:

```json
{
  "schema": 1,
  "adapter": "imessage-v1",
  "database": "/absolute/authorized/database.sqlite",
  "start": "2001-01-01T00:00:00Z",
  "end": "2001-01-31T00:00:00Z",
  "page_size": 100,
  "after": 0,
  "upper": null,
  "excluded_chats": [],
  "self_names": ["Sample User"]
}
```

The example dates and identity are synthetic. The operator supplies actual
scope; no default personal path exists. Windows are half-open, timezone-aware,
and at most 366 days. Pages contain at most 100 examined message rows.
The managed CLI starts at zero and owns subsequent cursors. A caller of
`run_page` may pass an explicit `after` and fixed `upper`; that low-level page
is independently bounded and does not prove an entire multi-page scan.

Supported shapes are explicit schema contracts, not universal app-version
claims:

- `imessage-v1`: `message`, `handle`, `chat`, `chat_message_join`, and
  `chat_handle_join`; message dates are nanoseconds since 2001-01-01 UTC.
  Required columns are listed in `_schema` in the reader. Ambiguous chat joins
  refuse attribution. Message GUID plus database, row, and chat identify a
  pointer; an app URL is not invented.
- `whatsapp-v1`: `ZWAMESSAGE` and `ZWACHATSESSION`, with the exact required
  columns in `_schema`; dates are seconds since the same epoch. Session type
  zero means direct and one means group in this named contract. Other shapes
  and enum values are unavailable until independently qualified.

Plain text is bounded at 256 KiB. A restricted binary NSKeyedArchiver plist
can supply `NSString` or `NS.string` through bounded UID references. The reader
checks the binary object count before parsing, rejects cycles and unsupported
structures, and never instantiates archived classes. Typedstream, XML archives,
compressed bodies, and attachment extraction are unsupported. A decoding gap
prevents the watermark from advancing.

## SQLite and file behavior

The parent stages only its reader program and exact request in fresh owned
state. It invokes the existing `evaluation_artifacts._sandbox_command` and
`coordination_process.run` owners. The database directory is read-only and only
the fresh worker directory is writable. The worker observes denied write-open
on the main file and existing sidecars before opening SQLite with `mode=ro`.
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
File identity, size and modification/change times bind the main/WAL generation;
SHM coordination identity is checked separately. Atime changes caused by reads
are not reported as data changes. A managed multi-page scan requires the same
generation throughout and rechecks even a completed replay before reporting it
current. This is a filesystem generation check, not a cryptographic proof
against a privileged malicious writer. Ordinary concurrent writers may cause
an honest refusal. No database-wide hashing or copying is performed.

## Durable output

Output is a bounded page of candidate notes and pointers plus examined range,
skip counts, gaps, schema binding, and source generation. Candidate categories
are heuristic. No raw message body or media bytes enter the result. Exclusion
and window tests precede logical body fetch/decoding; SQLite may read storage
pages containing neighboring data internally.

State directories must be physical, current-user-owned and mode 0700. An
exclusive lock prevents concurrent cursor owners. Descriptor-bound atomic
writes retain each pointer page before the checkpoint. A crash after storing a
page but before storing its cursor can replay the same page; different bytes
refuse reconciliation. A crash after cursor commit does not lose notes: all
`page-*.json` receipts remain. The last completed page can be replayed without
another read only while the source generation is unchanged. Retain state and
attempt evidence; do not silently adopt an unknown directory.

This scan cannot reconstruct deletions, edits between historical generations,
unsynced messages, unsupported schemas, structured group mentions, or a whole
conversation's meaning. Those limits remain visible in review coverage.


## Outbound recovery

The native outbound query is a separate named schema and bounded cursor, described
in [the Messages contract](messages-boundary.md). It reuses this reader's body
decoder, physical-path checks, source-generation checks, OS sandbox and process
owners. It retains only outbound row pointers/status and the exact approved
request in private attempt state. It does not expand the triage reader's windows
or establish missing historical coverage.
