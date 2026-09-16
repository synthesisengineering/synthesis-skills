# Coordination archive

`coordination.py archive` runs at day-start. Only rows explicitly marked
`released`, with an offset-bearing heartbeat strictly older than thirty days,
are eligible. Time is not evidence that an active claim ended. Unknown, naive,
future and exact-cutoff times remain. This command does not release claims.

Old addressed messages move only when exact, unambiguous sender and recipient
identities are both archived. Broadcasts, project/free addresses, active
participants and uncertain boundaries remain. Native-looking headings inside
fenced quotations are body text. Blocks containing non-message audit headings
remain intact, including administrative release records. Raw row and message
bytes, ordering and duplicate multiplicity are retained in monthly Markdown
files with byte-length and SHA-256 entry framing. An archived identity remains
available when a later closed exchange becomes eligible.

## Leased boards

Every attempt fetches under the normal board lock, validates prior archive
ancestry and tree members, and replans from that exact board. The board commit
keeps its one-file tree. Its `Archive:` header names a separate commit with
flat `YYYY-MM.md` blob members; that commit is the second parent of the board
CAS commit. The archive commit retains the preceding archive commit as parent.
One conditional remote ref update therefore publishes board removal and
reachable recovery evidence together. Ordinary subsequent writers retain the
header and commit ancestry. Invalid, missing or unreachable archive objects
refuse the operation. Failed CAS attempts remove no local rows or archive files.

`active-sessions.archive/` is a verified local mirror. A fresh machine can
hydrate it from the same lease ref. A crash after publication is recovered by
rerunning archive. Local files must match complete prefixes of published
history; drift, symlinks and invalid entries refuse replacement. Unrelated
files in the directory are retained. Git's normal remote durability is the
remote publication boundary; no stronger remote hardware guarantee is claimed.

## Unleased boards

The same local board lock protects a write-before-remove journal. Monthly
evidence and its directory entries are durable before board removal. The
updated board directory entry is durable before journal deletion. A retry
accepts only the exact original or completed board digest; divergence retains
the journal for reconciliation. A board that declares a lease cannot silently
switch to this local path when its configuration is missing.

`--dry-run --json` reports eligibility without changing the board or monthly
mirrors. Lease fetches may update the local bare repository. Maintenance
failure remains visible and never authorizes discarding evidence or releasing
another session's claim.
