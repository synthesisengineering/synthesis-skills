# Verified public execution and interpreter pin

Setup establishes one active materialized release and one absolute interpreter.
On macOS the prescribed interpreter is python.org Python 3.12.3 at
`/Library/Frameworks/Python.framework/Versions/3.12/bin/python3`; other supported
platforms use the CI-validated Python 3.12 family. Setup records the absolute
executable, its resolved target, binary SHA-256, exact version and platform in
the active release descriptor. An ambient `python3` on `PATH` is not an installed
execution authority.

The managed `synthesis` launcher has that absolute interpreter in its shebang
and disables bytecode writes. It contains the standalone, standard-library-only
`release_runtime.py` implementation. Before execution it verifies the active
descriptor, materialized tree digest and manifests, interpreter identity, and
launcher receipt. Symlinks, a source checkout, missing setup evidence, modified
bytes, malformed provenance and `SYNTHESIS_PUBLIC_SKILLS_SOURCE` overrides refuse.
No active-release failure falls back to a canonical checkout or plugin cache.

`synthesis exec-public` accepts a declared public script from this verified
release. It preserves child stdout/stderr bytes and exit status. Only an explicit
attention-code adapter for exit 1 may convert that status to success. Runtime
refusal, child startup failure and timeout remain exit 2. Child execution uses
`sys.executable` with `-B`; a hostile `PATH` cannot select another Python. Pipes
and regular files supply their exact stdin payload; held-open harness sockets
have a bounded read deadline. This is the existing Python launcher's execution
route; it does not add the excluded native dispatcher or a hook/gate API.

Private consumers verify the launcher's receipt hash before importing its
standalone runtime. They resolve scripts and implementation hashes against the
same active release, then execute children directly with the validated current
interpreter. The retired canonical-source runner is not retained as a shim.
Private rule-sync and adapter subprocesses also use the current interpreter.

## Setup and activation order

A plugin-only installation can establish this contract with skills-only setup;
full-feature enrollment is not required. The sequence is:

1. Acquire and verify the release, materialize its immutable generation, and run
   setup with the prescribed interpreter.
2. Record the interpreter and managed launcher before activating hook commands
   that require them. A missing launcher/setup pin fails explicitly.
3. Prepare client hook commands while preserving event slots, matchers,
   timeouts and protective semantics. Public commands use the managed launcher;
   private direct commands use the prescribed absolute interpreter.
4. Complete installed doctor checks and the separate client activation/trust
   gates. Source validation does not claim that installed commands or a native
   client session have changed.

The launcher's interpreter and implementation can change during a managed
upgrade. Exact previous generated launcher bytes, or bytes matching the prior
setup receipt, establish ownership; a marker alone does not. Activation holds
the descriptor lock and records a recovery journal before replacing the
launcher/pointer pair. An ordinary failure restores the exact old pair. A crash
leaves an explicit pending journal; new execution refuses until setup recovers
the recorded pair. Unrelated local modifications prevent recovery from
overwriting them. Later release updates with unchanged launcher bytes need only
the atomic active-pointer replacement.

## Doctor and evidence boundaries

Installed doctor verifies the executable path, target, version and binary hash,
the launcher bytes/shebang, and any guardian service declaration's interpreter.
Private installed doctor also checks every private hook command against the
recorded pin. Source doctor validates source command wiring independently of
installed activation; an older installed release does not make valid candidate
source fail its source-only checks.

The fixture contract covers missing/corrupt/drifted roots, source overrides,
unknown launcher edits, a true interrupted migration, recovery, hostile PATH,
entrypoint containment, exact stdin bytes, held-open sockets, explicit attention
handling, timeout/start failures and guardian/launcher drift. Source tests and
receipts do not replace fresh Claude and Codex native acceptance after their
separate activation and trust gates.
