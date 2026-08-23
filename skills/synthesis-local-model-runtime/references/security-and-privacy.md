# Security and Privacy

## Identifier minimization

The profiler uses allowlists. Raw `system_profiler`, WMI, registry, or firmware
output must never be persisted because those surfaces may include serials,
UUIDs, account names, and device identifiers. Tests scan serialized output for
forbidden key and value patterns.

## Storage boundaries

Resolve paths before comparison. Reject a model store located inside:

- the current user's iCloud Drive and CloudStorage roots;
- `~/workspaces` by default;
- a caller-supplied protected root;
- the current Git repository when detected.

Do not infer that a symlink points somewhere safe from its visible prefix.

## Downloads and subprocesses

- Execute runtime CLIs with argument arrays and `shell=False`.
- Never include credentials in runtime model ids, URLs, logs, or inventories.
- Do not download arbitrary URLs from policy files. Catalog entries are the
  executable allowlist.
- A pull is successful only after the runtime enumerates the artifact.
- Capture the resolved digest. Do not claim an expected digest matched when the
  runtime returns none.
- Preserve partial-download diagnostics, but do not write a false installed
  record.

## Local API

Generation and metadata calls use loopback HTTP only. The executable has no
option to send prompts to a remote host. A future remote adapter is a separate
capability and requires its own disclosure and credential review.
