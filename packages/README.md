# Synthesis package distribution

Homebrew, npm and Bun install the same small `synthesis` command. The package
contains the release's bootstrap, source commit, source-tree SHA-256, bootstrap SHA-256 and an
acquisition wrapper. It does not contain the optional skill catalog, run install
scripts, register hooks, change an agent configuration or start services.

The command supports macOS and Linux. Python 3.12–3.14 and Git are required.
Homebrew declares those runtime dependencies. npm and Bun users can ask
their agent to verify/install these prerequisites before setup.

## Build and publication

After the gated source release has produced a clean exact version tag:

```sh
python3 -B packages/build.py --repo-root . --output /absolute/new/artifact-directory
```

The builder refuses an untagged or dirty release and an existing destination.
It produces an npm package directory, a deterministic portable command archive,
a Homebrew formula, a prepared unpublished AUR PKGBUILD and channel metadata with actual checksums.
The archive is a script-based command with declared dependencies, not a
self-contained native executable. No artifact is uploaded by the builder.

Publish the archive at the generated GitHub release URL before the formula.
Pack and publish the generated npm directory once; Bun consumes the same registry
package. AUR registration/publication is deferred and is not an installation
option in this release. Its recipe remains prepared for future work.
Verify ordinary registry URLs and fresh consumer installation after each
publication. Source templates and local pack tests do not prove publication.

The package owns its executable under the package manager's prefix. Setup puts
the verified managed launcher in the separate XDG data directory
`synthesis/bin/synthesis`. This avoids overwriting npm/Homebrew/AUR-owned bins.
An existing active descriptor identifies the managed launcher for diagnostics
and lifecycle commands. The package-owned verifier checks the active generation,
interpreter and tree before dispatching the declared CLI; it never executes a
launcher solely because its mutable receipt lists a matching hash. Cached core
activation additionally requires the source-tree digest embedded in the package.

Setup uses the package's exact source version and commit. To adopt a new package
release, upgrade the package and run setup again. A user can separately choose
a different lifecycle channel through the managed setup interface. No background
updater is installed by the package.

## Modular adoption

`synthesis setup --profile modular --skill NAME` selects a skill and its declared
dependencies. Optional core files remain outside agent discovery until explicit
activation. `--no-dormant-core` omits those optional files from the materialized
generation and from selection-owned staging. Its acquisition uses a temporary
Git mirror that is removed after verification. Existing shared installations
and source caches remain owned by their existing selections.

The reduced generation records both its exact file inventory/digest and the
original verified release's content digest/commit. Required installer/runtime
bytes still occupy disk. Opt-out does not erase package-manager files or pretend
that required runtime code has zero storage cost.

For standalone tools, `synthesis stage-core --for-tool TOOL --no-dormant-core`
is a local declined response. It needs only Python 3.9 or newer and does not
acquire source, require Git, install a runtime, or write a receipt. Existing
staged payloads and receipts are preserved. Default tool staging and ecosystem
setup require Python 3.12–3.14 and Git.

## Consumer acceptance

`test_distribution.py` includes real isolated npm and Bun installs with scripts
disabled, wrapper execution from an unrelated working directory, no home
enrollment, corruption refusal, exact profile forwarding, release projection and
interpreter drift. The distribution CI matrix covers Python 3.12–3.14 on macOS
and Linux. An optional manually dispatched Arch job can build a checksum-bound candidate recipe;
ordinary upstream download acceptance follows publication.
