# Bounded journal storage

The run journal owns durable state, command replay, native observation custody
and the event chain. Large snapshots use content-addressed blocks under the
same run directory. The storage codec introduces no actor, scheduling service,
claim, model budget or permission authority.

A snapshot above 1 MiB is represented by a descriptor containing the root block
digest, complete logical JSON digest and exact logical byte count. Blocks carry
JSON fragments and references. Dictionary partitions use hashes of their keys,
so unrelated changes can reuse retained fragments. Lists and strings are split
in order. No observation, cursor, event index, failed result or prior event is
removed during encoding. The event's existing logical digest remains unchanged.

The admitted writer holds the existing run lock and checks the complete event
and projection block set before committing. It installs immutable blocks,
flushes each file and the containing directory, then commits the event. Derived
projections follow. A crash before event commit can leave unreferenced blocks;
they confer no state and still count against capacity. A crash after commit is
recovered through ordinary same-command replay or projection rebuild. It does
not replay an external effect.

Readers authenticate every referenced block, reject links and nonregular files,
check expanded size and reference/depth bounds, and recheck the logical content
digest. Missing or changed blocks make the journal unverifiable. Readers retain
support for existing inline historical events because those original bytes and
digests remain the historical authority; they are never rewritten as migration.

| Bound | Value | Purpose |
|---|---:|---|
| Inline snapshot | 1 MiB | Switch storage representation before the former file-size boundary |
| Leaf JSON | 64 KiB | Bound individual decoded fragments |
| Physical block | 128 KiB | Allow framing while bounding each file read |
| Logical snapshot | 64 MiB | Bound an admitted operation's total retained state |
| Native projection share | 32 MiB | Reserve room for the index, cursor, latest batch and other owners |
| References in one read | 16,384 | Bound malicious expansion and traversal |
| Codec depth | 64 | Bound recursive representation processing |
| Store bytes per run | 512 MiB | Bound cumulative immutable retention, including orphans |
| Store entries per run | 32,768 | Bound directory work and inode use |

The existing 10,000 journal-event and 10,000 native-index limits remain. Reaching
any bound refuses the next append with the previous committed state and cursor
intact. The owner must plan an explicitly linked bounded continuation; deleting
history or manufacturing a successful observation cannot satisfy that refusal.

Native event consumption retrieves the exact historical batch through the
block tree and compares its digest to the already authenticated current event
index. This avoids reading a complete growing snapshot for every selected old
observation. Every physical read counts against the existing 8 MiB consumption
budget. That component lookup proves only the selected batch; full-chain
validation remains with the run owner. The operator view keeps its existing
two-second verification budget and never turns a timeout into a partial PASS.

Prepared native launch attribution derives both descriptor and block bytes from
the committed owner state. The ordinary repository attribution owner verifies
those bytes; a block-shaped filename grants no ownership of unrelated edits.

After installing a release with this codec, recover the existing run through
its normal authenticated owner. Read the last committed revision, preserve the
failed append evidence, and continue observation from the retained cursor. No
manual migration, snapshot deletion, cursor edit or native permission change
is needed.
