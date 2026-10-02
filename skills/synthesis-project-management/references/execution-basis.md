# Complete execution evidence at project scale

An execution basis binds the retained project bytes used by an admitted
autopilot run. It does not replace project management's whole-project checkpoint
or grant run ownership, action authority, native capability or task completion.

The execution receipt carries file-commitment schema 3 with a framed SHA-256
commitment to each member's relative name and type. Regular files bind their
normalized size and complete contents. Retained symlinks bind their link text
and inode metadata; FIFOs, sockets and device entries bind their type and inode
metadata. These custody-only members are never opened or followed as execution
inputs. Unowned directories, including empty directories, bind their names and
permissions. A second commitment
omits only the explicitly named CURRENT_STATE record and carries the context
record separately for the existing verified terminal-state successor check.
The selected run's owner-verified journal projections and digest-addressed
managed inputs retain their established derivation rules. Other runs, archives
and unknown evidence files stay included.

The inventory reads arbitrary evidence in chunks of at most 1 MiB. Semantic
documents and structured inputs retain their separate 16 MiB parsing bound.
Directory-descriptor traversal and before/after identity checks reject linked
project ancestors, changed directory membership, replacement, truncation and
growth. The plan, journal projections and immutable inputs must remain regular
files. Directory paths derived from the selected journal and inputs are owned
by their exact derivations; unrelated directories and evidence remain included.
A complete second metadata pass checks for observed changes after a file was
hashed. This is observed consistency, not an atomic filesystem snapshot against
an arbitrary concurrently hostile process.

Each operation permits at most 250,000 entry visits across both passes, 16 GiB
of streamed contents and 128 directory levels, with a checked 120-second
monotonic deadline. Saturation refuses the operation. It never returns a
partial inventory or silently omits large files. The deadline is cooperative
around local filesystem calls; it cannot cancel an indefinitely blocked kernel
filesystem operation.

Larger observations require a managed immutable input selected explicitly by
the existing `checkpoint` operation's `inventory_policy_id`. Its typed JSON is:

```json
{
  "schema_version": 1,
  "kind": "execution-inventory-policy",
  "limits": {"entries": 2000000, "bytes": 17179869184, "seconds": 240, "depth": 128}
}
```

Materialize the value through the existing `input.materialize` owner. Every
limit must be a positive integer. Supported ceilings are 4,000,000 entry visits
across both passes, 64 GiB, 300 seconds and 128 directory levels. A policy is a
processing budget, never ownership or permission. The receipt binds its input
ID, path, digest and limits into the file commitment. Validation re-reads the
immutable policy and the entire project. No inventory cache is accepted.

Automatic checkpoints retain the explicitly selected policy from the current
checkpoint journal. Passing `inventory_policy_id: null` explicitly restores the
default bounds. Profile evidence uses the same selection. An unselected project
always uses the protective defaults; no environment variable or discovered
policy file can raise them. A policy applies to each complete inventory, so a
caller that performs several inventories must also bound its aggregate work.

Validation re-observes the complete inventory. A changed, added, renamed or
missing member invalidates the commitment. Current proof reporting uses the
same fresh inventory that it validated, avoiding a second complete inventory.
A successful terminal PM successor
requires the existing ordinary owner proof, unchanged operational fields and
the complete non-state commitment; changing the aggregate digest in a receipt
does not manufacture valid evidence.

Older execution receipts require fresh capture through the existing admitted
checkpoint or recovery owner. They are not silently converted. Retain the old
receipt and any failed recovery prefix; reconcile the actual journal before
retrying an interrupted request. Never reset costs, deadlines or unfinished
obligations to obtain a new receipt.
