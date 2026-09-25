# Complete execution evidence at project scale

An execution basis binds the retained project bytes used by an admitted
autopilot run. It does not replace project management's whole-project checkpoint
or grant run ownership, action authority, native capability or task completion.

Receipt schema 2 carries a framed SHA-256 commitment to every ordinary file's
relative name, normalized size and complete contents. A second commitment
omits only the explicitly named CURRENT_STATE record and carries the context
record separately for the existing verified terminal-state successor check.
The selected run's owner-verified journal projections and digest-addressed
managed inputs retain their established derivation rules. Other runs, archives
and unknown evidence files stay included.

The inventory reads arbitrary evidence in chunks of at most 1 MiB. Semantic
documents and structured inputs retain their separate 16 MiB parsing bound.
Directory-descriptor traversal and before/after identity checks reject links,
special files, changed directory membership, replacement, truncation and growth.
A complete second metadata pass checks for observed changes after a file was
hashed. This is observed consistency, not an atomic filesystem snapshot against
an arbitrary concurrently hostile process.

Each operation permits at most 250,000 entry visits across both passes, 16 GiB
of streamed contents and 128 directory levels, with a checked 120-second
monotonic deadline. Saturation refuses the operation. It never returns a
partial inventory or silently omits large files. The deadline is cooperative
around local filesystem calls; it cannot cancel an indefinitely blocked kernel
filesystem operation.

Validation re-observes the complete inventory. A changed, added, renamed or
missing file invalidates the commitment. A successful terminal PM successor
requires the existing ordinary owner proof, unchanged operational fields and
the complete non-state commitment; changing the aggregate digest in a receipt
does not manufacture valid evidence.

Older execution receipts require fresh capture through the existing admitted
checkpoint or recovery owner. They are not silently converted. Retain the old
receipt and any failed recovery prefix; reconcile the actual journal before
retrying an interrupted request. Never reset costs, deadlines or unfinished
obligations to obtain a new receipt.
