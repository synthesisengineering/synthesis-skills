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
- Treat LM Studio's allowlisted metadata hash as `runtime-metadata`, never as a
  content digest. Multiple catalog matches are an error.
- Model updates require an explicit installed name list or explicit `--all`,
  remain dry-run without `--yes`, and re-enumerate after every native pull.
  Record identical digest and size as `already-current`; do not infer freshness
  from command success alone.
- Preserve partial-download diagnostics, but do not write a false installed
  record.
- A registry-timeout recovery must use only catalog-pinned cached GGUF layers,
  verify their full SHA-256 digests and exact sizes, and create same-volume
  temporary hard links. `--recover-cached` must skip acquisition rather than
  retrying the failed registry request. Never accept a filename or a completed
  progress bar as content verification.
- Do not delete a retained registry blob from the runtime-owned store. Report
  it as possible reclaimable cache; cleanup requires a separate, bounded
  reference audit and explicit authorization.

LM Studio downloads use only catalog-owned Hugging Face targets through
`lms get ... --yes --gguf` or `--mlx`. Policy files cannot inject model URLs.
The adapter parses `lms ls --json --variants`, emits only allowlisted metadata,
and removes absolute path prefixes before inventory output.

## Local API

Generation and metadata calls use loopback HTTP only. The executable has no
option to send prompts to a remote host. A future remote adapter is a separate
capability and requires its own disclosure and credential review.

HTTP error bodies are preserved only up to a fixed bound so architecture and
cache incompatibilities remain diagnosable without allowing an unbounded local
service response into logs.

## Runtime service changes

Runtime configuration is dry-run-first and requires `--yes`. The Homebrew
adapter rejects symlinks, foreign ownership, unexpected labels, unexpected
commands, and values outside its KV-cache allowlist. It writes atomically,
stores the original plist under the private state directory, and restores that
original if unload, reload, or health verification fails. It never edits the
Homebrew formula or a system-wide service.
