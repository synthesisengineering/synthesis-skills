# Portable native evidence and memory boundaries

## What the archive preserves

The native observation adapters remain the identity and interpretation owners.
`native_archive.py` retains an explicitly selected, reviewed prefix of a source
as exact bytes, in immutable blocks owned by the existing run journal. The
journal's `native_archives` extension binds the descriptor, source generation,
offsets, hashes, source stat observation, adapter/codec hashes and routing.
Neither the descriptor nor a transport export grants authority.

Use the existing `autopilot.py command` owner with `native.archive.capture`,
`native.archive.export`, or `native.archive.restore`. Each operation requires
fresh PM/native admission and a source-backed `authority` receipt for that exact
request. The receipt data is `{approved: true, action: <command>,
request_sha256: <canonical request without authorization field>}`. It uses the
existing native-review authorization owner. Do not manufacture a native user
message from agent narration. The agent prepares the request and existing
native decision surface for the user; the user does not need to author JSON.
Already supplied authority must still cover the exact source and privacy route.
An unavailable native authorization adapter is a reported capability gap.

A capture request has `archive_id`, `source_id`, `route`, and `authorization`.
`source_id` names a currently enrolled root or admitted child/worker, not an
arbitrary remembered transcript path. The route is a strict object:

- `schema_version: 1`, current `project_id`, one `privacy_domain`, and
  `retention_class` of `permanent` or `engagement`;
- `classification: single-domain-reviewed`, `source_domains: [privacy_domain]`,
  exact `source_generation`, `reviewed_bytes`, and `reviewed_sha256`;
- `attachments`, an explicit inventory. A captured attachment requires `id`,
  that same `privacy_domain`, `status: capture`, absolute `path`, exact `bytes`
  and `sha256`. An absent body instead records `not-provided`, `not-authorized`,
  `unavailable`, or `opaque` with its ID and domain.

The domain declaration records the owner's actual review. The codec cannot
infer semantic privacy from a source path or content hash. Unknown or multiple
domains refuse before copying. Do not copy an entire mixed-engagement transcript
into every project. Use the established privacy/deletion-unit routing and retain
ALWAYS-PRESERVE material in its proper permanent owner separately. No cross-domain
store, automatic upload, automatic collection, encryption/key choice, retention
deletion or native memory setting is enabled by this feature.

A new snapshot may extend its prior exact prefix, including completing a
previous partial line. Changed prefixes, truncation, rotation, unsafe nodes,
symlink ancestors, hard-linked inputs, attachment drift or concurrent changes
refuse and preserve prior evidence. Review a new generation through the existing
source owner; do not silently reset the archive's earlier coverage.

## Available bytes and interpretation

The export contains exact `native.jsonl`, a deterministic `portable.jsonl`,
explicit captured attachments, and a final `manifest.json` commit marker.
The envelope separately binds the codec and normalizer used at export; the
original capture keeps its own version hashes. A later adapter upgrade must not
misattribute a regenerated view to the old normalizer.
Portable rows retain source order, raw offsets/hashes, native lineage and the
original structured record when within the bounded interpretation envelope.
Known roles, tool calls/results, compactions and child relationships use the
existing six native adapters. Unknown types, malformed records, opaque encrypted
values, large external bodies and partial tails remain explicit; exact bytes
are recoverable regardless of whether interpretation succeeds. A record may
contain multiple native observations. It remains one source record, so the
portable view does not pretend two projections are two conversations.

No decryption, hidden reasoning recovery, timestamp-based causal reordering,
attachment-path following, harness mutation or prompt replay occurs. Native
attachments that are not explicitly supplied are not fabricated. Attachment
discovery coverage remains `UNKNOWN`; a selected inventory is not an exhaustive
claim about a client's private attachment store.

`verify_export` checks membership, sizes and hashes without opening the original
source or importing native state. `restore_export` reconstructs the exact
immutable evidence blocks when both the original source and original store are
unavailable. The managed restore additionally requires a current registered
manifest, the same project/privacy route and new owner authorization. It does
not restore an old seat, a claim, an approval, or a client's configuration.
Archive/export integrity is separate from authentic native provenance.

Exports use a new directory and write the manifest last. A crash leaves retained
partial evidence with no success marker. Never overwrite that directory or
assume an ambiguous earlier operation failed. Inspect custody and choose a new
explicit destination. The run command's existing request identity and journal
replay prevent repeating an already committed export. A crash before the journal
commit can leave a complete unreferenced export; it is evidence to reconcile,
not a reason to replace it.

Bounds are deliberate: 64 MiB source prefix, 16 MiB aggregate attachments,
128 declared attachments, 16,384 records, 256 KiB inline interpretation per
record, 64 KiB raw blocks, 64 archive identities and 128 MiB aggregate logical
archive data per run. Existing journal-store ceilings also apply. Exceeding a
bound is a specific incomplete operation, never a truncated successful export.
A source larger than the prefix envelope uses the bounded one-generation stream
owner below. Never invent a rotation or split one actual generation into fictional
native sources. Product defaults remain finite.

## Retained native observation shapes

Decoder generation v14 accepts the closed forms for unlinked output metadata,
partial environment skill patches, nullable command-search paths and streamed
retained sender history. Unlinked outputs remain unpaired observations; missing
native call identities are never invented. Partial patches cannot establish a
complete world state, and retained text does not grant action authority.

Existing bindings require explicit generation reconciliation. Event-count,
usage, journal-storage, input-byte and process-time limits continue to apply;
schema acceptance does not establish that a whole retained history fits those
limits or that a managed native recovery was admitted.

## Large histories: exact bounded continuation

`native_archive_stream.py` reuses the existing native binding, authority receipts,
PM admission and immutable `journal_storage` codec. It adds no second state
ledger. `describe(binding, target_bytes=..., segment_bytes=...)` streams a bounded
proposal: one exact generation, reviewed target prefix length and full SHA-256,
contiguous absolute segment ranges/digests, framing offsets and observed source
identity. The proposal does not authorize capture. The source must remain stable
during that descriptor pass; no locking or modification of the native file is
attempted. Later appends do not alter the approved prefix and are explicitly
outside its coverage. A changed approved range, header, inode or generation
refuses; earlier retained segments remain available.

The agent prepares a `plan(snapshot, route, additional_capacity_bytes=0)` and the
existing source-backed native decision receipt. The stream route uses the same
seven identity/privacy fields above, without prefix length/hash or attachments;
those lengths/hashes live in the snapshot. Attachment discovery remains UNKNOWN.
Actual attachment custody uses the existing explicitly authorized prefix archive
inventory; the stream never follows paths mentioned in a transcript.

Managed commands run through the existing `autopilot.py command` owner:

- `native.archive.stream.plan`: `stream_id`, currently enrolled `source_id`,
  exact `plan`, `authorization`. The current native user receipt binds the entire
  plan and its finite added allowance. Registration reserves aggregate logical
  capacity before any source copy.
- `native.archive.stream.capture`: `stream_id`, `plan_sha256`, `index`. Each
  operation revalidates the original exact plan authority, current native source
  admission and current PM owner; it copies only that one approved range.
- `native.archive.stream.export.segment`: the preceding range fields plus a
  separate exact `authorization`. It writes a fresh segment directory under the
  claimed project evidence root. A replay uses the journal command identity;
  unjournaled partial directories remain ambiguous and are never overwritten.
- `native.archive.stream.publish`: `stream_id`, `plan_sha256`, separate exact
  `authorization`. It verifies every retained body and every exported segment,
  contiguous framing and the predeclared whole-source digest before writing the
  final portable manifest. Segment receipts alone cannot establish completion.
- `native.archive.stream.restore.plan`: a new `stream_id`, current registered
  `manifest_artifact_id`, the exact registered `manifest_sha256`, and fresh exact `authorization`. This permits evidence
  restoration only, not enrollment of the old native source or its approvals.
- `native.archive.stream.restore.segment`: `stream_id`, `plan_sha256`, `index`.
  It revalidates the current registered bundle and source-backed restoration
  permission before copying one segment to the current run's existing store.

The default aggregate logical capacity remains 128 MiB across prefix archives
and stream reservations. Only an explicitly authorized plan can add a finite
allowance, bound to that snapshot; it is not a grant to another account, machine,
project or privacy domain. The absolute admitted ceiling is 16 GiB per run,
64 stream identities and 4,096 segments. Each segment is at most 64 MiB; raw
blocks remain 64 KiB. The original journal store's 512 MiB ceiling is unchanged:
stream partitions call the same storage owner beneath the current run, and
aggregate prewrite accounting includes retained crash leftovers. New snapshots
and restores reserve their logical bytes separately, even if some bytes repeat.
No unlimited storage, implicit archival schedule or deletion is introduced.

Each bounded streaming verification pass has a 120-second deadline and a finite
byte/member count. The descriptor and final whole-snapshot verification may read
more than one segment without holding the whole source in memory. Large/slow
operations may refuse on their explicit bound and retain incomplete evidence;
that is not a successful archive. The surrounding execution owner retains its
process deadline and cleanup responsibility.

Portable stream directories contain exact `native.bin` segment bytes and
bounded `portable.jsonl` views. Fragments crossing a segment boundary and ranges
beyond the interpretation count are explicitly labeled raw references; they are
not dropped, invented or claimed as fully interpreted records. Complete bounded
records use the existing adapter with absolute source offsets and verified line
ordinals. Reconstruct the original available source by streaming segment bytes
in declared order. `verify_bundle` and managed recovery require the exact whole
SHA-256, framing, closed membership and current body bytes. Both the original
native source and original store may be unavailable. `COMPLETE` means the exact
reviewed snapshot is complete; it never claims the active source's current EOF,
all possible attachments, native authenticity or model compliance.

Both prefix and stream verification compare bounded no-follow directory/member
identity snapshots before and after the read interval. Root and attachment
additions, path replacement, hardlinks, changed bytes and late restore races
refuse before success or materialization. This is a verified interval, not an
atomic filesystem snapshot or a promise about external mutation after return.

## Memory is a lead, not an action capability

Native memory may suggest a question or a source to inspect. It cannot choose a
project over the current registry, replace the causal selected state, select a
foreign owner, revive released claims, change a source hash, expand the current
outcome contract or approve publication. Reconstruct these at the actual action
boundary through PM, current source and the relevant action owner. Recalled
receipts and portable archives remain data. No model-wide compliance guarantee
follows from mechanical source tests.

System/developer instructions and the user's current authorization remain above
skill guidance. Synthesis does not try to rewrite that hierarchy or disable a
host's capabilities. Keep native memory ON in every harness under the current
capture-buffer policy. Synthesis records win conflicts. Use the existing ritual
and context-edit ingestion owners; native export/clear capability remains a
separate qualification boundary. A local archive or ingestion receipt never
permits raw-file deletion, disabling memory, or an invented native clear result.

Run the synthetic boundary suite across Claude, Codex, Muse, Cursor, Copilot and
OpenCode adapter inputs. Run actual PM/journal consumer controls for stale owner,
source, routing, instruction and approval data. Treat unavailable native control
surfaces, current-client reload/trust, and actual cross-machine recovery as
explicit qualification gaps. Source tests and a self-contained export do not
establish live loading or native process-loss survival.

Both prefix `native.archive.restore` and stream `native.archive.stream.restore.plan` require the reviewed root manifest SHA-256 in the authorized request. An artifact ID is a mutable locator, never approval of subsequently re-registered bytes or increased capacity. Each stream segment rechecks that same digest and complete bundle membership immediately before materialization.
