# Preserved: `skills/synthesis-agent-conformance/references/hermes-cli-pilot.md` before v5 (verbatim)

Retired: Hermes is not one of v5's three harnesses (R9.3), and its adapter scripts were cut (install-release evaluation). Whether the movement project still wants a Hermes adapter is that project's decision.

## Contents of the preserved text

- Native contract and provenance
- Prepare, install and inspect through existing owners
- Recovery and the protective boundary
- Evidence and acceptance
- Admitted context-consumption observation

---

# Hermes CLI pilot contract

This is a source-qualified pilot for the official Hermes CLI shell-hook surface.
It does not enroll Hermes as an autonomous managed writer. Keep its capability
status prospective until a separately authorized real-client trial establishes
installed, delivered, live, continuity and outcome evidence.

## Native contract and provenance

The implementation is grounded in NousResearch/hermes-agent commit
`28e6496a5e3adfea57bebfc9571b981bff378523`, observed September 27, 2026:
[hooks](https://github.com/NousResearch/hermes-agent/blob/28e6496a5e3adfea57bebfc9571b981bff378523/agent/shell_hooks.py),
[skills](https://github.com/NousResearch/hermes-agent/blob/28e6496a5e3adfea57bebfc9571b981bff378523/website/docs/user-guide/features/skills.md),
and [session storage](https://github.com/NousResearch/hermes-agent/blob/28e6496a5e3adfea57bebfc9571b981bff378523/hermes_state_sessions.py).
Requalify this contract against later upstream revisions before claiming support.

The selected hooks are `pre_tool_call`, `pre_llm_call` and `on_session_start`.
Only the tool hook provides protection. The prompt hook supplies recovery
context. Session-start return values are ignored by Hermes; the callback can
retain a source observation but cannot prove that context reached the model.
The native shell owner launches an argv command without shell expansion.
The fragment keeps a finite 30-second timeout and `fail_closed: true` and never
sets `hooks_auto_accept` to true. Native hook consent stays with the user.

## Prepare, install and inspect through existing owners

Invoke the verified `synthesis exec-public` owner for
`synthesis-agent-conformance/scripts/hermes_adapter.py prepare`, with explicit
`--profile-home`, `--index`, `--project` and selected `--skill` values. The output
is an inert plan, not configuration activation. It binds the selected skill
contents and dependency closure, and names the existing source installer with
explicit `SYNTHESIS_SKILLS_TARGETS` and `SYNTHESIS_SKILLS_SELECT` values.
The existing `direct_copy.sh` owner retains backup, provenance and drift rules;
selection is validated before copying. It cannot authorize selected uninstall.
Merge only the reviewed hook fragment through the configuration owner and leave
unrelated native settings intact. This package performs neither action.

`inspect` checks every selected skill file against its source, excluding the
installer's own provenance record. Installed equality still leaves live loading
UNKNOWN. Client discovery honors the explicit `SYNTHESIS_HERMES_BIN` override;
a missing or empty explicit value never silently chooses another executable.

## Recovery and the protective boundary

The callback binds the exact CLI session ID, profile and working directory to a
bounded snapshot of the selected profile's `state.db` and optional WAL. It reads
session metadata only, never message bodies, and opens only copied database
bytes. It refuses foreign, closed, future, stale, child or ambiguous sessions,
unsafe ownership, aliases, changed inputs, malformed current-generation WAL checksums,
rollback journals and resource overflow. Limits are two
seconds and 128 MiB aggregate. A refusal does not authorize permission repair,
history truncation, another profile or removal of native safeguards.

Project recovery calls the canonical registry/worktree resolver and diagnostic
context renderer. It performs no fetch, branch update, lease refresh or message
acknowledgment. A causally newer worktree can be selected; stale prose cannot
replace that choice. Managed writer admission remains unsupported in this pilot.

The installed-artifact guard reuses the shared path and shell parser for the
native `terminal`, `write_file` and `patch` tools. Known malformed writes refuse;
both lexical installed paths and canonical aliases are checked. Hermes reports process cwd in callbacks while terminal/file tools retain a
separate persistent session cwd. Relative file and patch destinations therefore
refuse unless the actual native contract supplies that state; use explicit
absolute destinations. Terminal writes may use an explicit absolute `workdir`
or an explicit absolute `cd` proven by the shared parser. A caller-added `cwd`
or file-tool `workdir` hint is not native authority. Unknown persistent HOME
expansion refuses. Ordinary reads
retain native behavior. Other tool names retain native behavior and are NOT
covered by this guard, including alternative plugins and `skill_manage`.
This is one qualified protective boundary, not a claim of complete repository,
communication or arbitrary-plugin protection.

## Evidence and acceptance

The existing receipt owner may retain an exact callback source observation under
`agent-conformance/observations/hermes`. Its kind is
`callback-source-observation`, its native status is UNKNOWN, and it grants no
execution authority. It never updates the live-load state or masquerades as a
Claude/Codex SessionStart receipt. A forged direct invocation cannot become
native acceptance merely by creating this file.

Source tests cover actual pinned upstream response parsing, selected copying,
SQLite/WAL identity, real registry-first recovery, protected writes and verified
runtime dependency drift. They do not launch Hermes or a model. The real pilot
must separately observe native hook consent, a fresh CLI lifecycle callback,
context delivery, allowed read, protected-write refusal, interrupted/restarted
recovery and retained evidence on the exact installed release. Keep unsupported
native writer and gateway surfaces explicit; do not infer provider endorsement.

## Admitted context-consumption observation

The `native-context-observation` capability connects the existing PM dispatch,
worker receipt, native-source coverage and vendor consumer owners. It observes
an explicitly selected **existing** Hermes process. It never starts a model,
changes hook consent, executes a command, signals that process, or declares a
sandbox enforced. A successful child still requires its integration audit.

The admitted immutable selection has schema 1 and client `hermes`, plus the exact
`session_id`, `profile_home`, `profile`, `cwd`, `state_home`, `producer_version`,
`process`, `hook_argv` and `source_files`. Obtain process identity through the
transport owner, and explicitly review the executable/script SHA-256 inventory.
The existing PM file contract must register this one selection as immutable and
admit an owned scratch directory with a Unix socket path of at most 100 bytes.
No process or source selection may be inferred from a callback's own payload.

The ordinary `prepare` owner accepts an optional `--capture-socket` argument.
It adds the supported `pre_api_request` observer to the inert hook fragment and
binds both callbacks to that private channel. Approval and activation remain
separate from preparing the fragment. Start the admitted PM `native_worker`
observation before the existing selected native process begins its selected
turn; its finite listener waits for exactly one `pre_llm_call`/`pre_api_request`
pair. Native OS peer PID/UID, retained process birth/direct parent identity, selected command
metadata and pinned source bytes bind the local transport. The process metadata
uses the platform's `ps` command representation, not a kernel argument-vector
attestation; native qualification must establish the exact selected invocation.
This is not protection against a hostile host user with the same UID.

The pre-prompt callback records an explicitly non-authoritative candidate in the
existing Hermes source-observation registry, then appends its exact event/hash
marker to its context. The later observer captures the assembled request through
Hermes's actual pre-API hook. The consumer joins exact session/profile/turn,
source and installed generation, current PM receipt and complete source coverage,
registry bytes and freshness. It accepts the actual `messages` or `input` wire
and supported text blocks, refusing truncation, duplicate markers or ambiguous
message fields. Context must fit the 6,000-byte capture bound; a larger or
vendor-truncated request remains UNKNOWN. Each raw frame is retained under the
worker receipt, including bounded malformed or interrupted input.

`native.enroll` and `native.observe` use the existing `worker:<child-id>` source.
The vendor consumer's selection uses the existing PM fields and both exact event
IDs; for Hermes, `registry_latest` selects the admitted `state_home` registry
root. A qualified result is scoped to
`admitted-hermes-context-consumption-only`. Direct registry records, caller JSON,
a parsed transcript or a signature alone cannot satisfy that consumer.
Permissions, model-turn completion, protected execution, cold recovery and live
desktop loading remain separate UNKNOWN results. The managed invocation and
complete tool/permission boundary still require implementation and actual native
qualification; this context capability does not close those obligations.

The current upstream shell-hook producer uses direct `Popen(shell=False)`.
The admitted peer must have the selected native process as its immediate parent;
a tool-created grandchild with the same hook command is refused before payload
retention. Process metadata is revalidated before and after capture. This is
source-bound local custody, not a kernel argv attestation or a defense against
arbitrary same-UID modification of the trusted native process.

Exact raw frames are retained separately from metadata, with a 1 MiB transport
frame limit. Native observation retains its existing 256 KiB default record
limit: larger complete raw transport can therefore have incomplete semantic
coverage, and the vendor consumer returns UNKNOWN. Neither limit is raised.
