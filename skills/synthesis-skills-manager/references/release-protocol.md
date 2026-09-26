# Gated release protocol and required checks

## `release.py` — the gated cross-client plugin release

For the **public plugin**, steps 3–7 of the protocol below are automated by
`scripts/release.py`, which exists because that sequence has exactly one
failure mode that matters and it is silent: the repository is the plugin (the
marketplace manifests carry no version and point at `./`), so pushing IS
publishing — but each client keeps a **version-pinned installation that does
not follow the remote**. A pushed-but-uninstalled release leaves the running
clients behind their own source with nothing visibly wrong.

```bash
python3 skills/synthesis-skills-manager/scripts/release.py --repo-root .
python3 .../release.py --dry-run       # print the plan, mutate nothing
python3 .../release.py --check-only    # preflight + required checks, no publish
python3 .../release.py --acceptance-only # consume the bound acceptance result (CI)
python3 .../release.py --install-only  # refresh + verify clients (new machine, drift recovery)
```

The sequence, each stage gating the next:

**preflight → required checks → publish → activate public CLI → install selected clients → verify → reconcile lifecycle**

- **Preflight** refuses to proceed unless all three plugin manifests agree, the
  newest CHANGELOG entry matches them, and the tree is clean. It also refuses
  to run against an installed cache mistaken for the source checkout.
- **Acceptance consumption** derives the base-to-head change universe from
  Git at the release boundary, requires exact manifest coverage, and parses a
  fresh result bound to a one-use transaction, head commit and tree, manifest
  digest, and changed-path digest. The boundary recomputes those fields and
  rechecks the clean worktree before it can authorize publication. The
  accepted-state object survives the check phase and expires when any binding
  changes. CI invokes the same consumer with the pull request base supplied by
  its event record.
- **Publish** revalidates the accepted state immediately before every remote
  mutation and atomically pushes the immutable accepted commit SHA to three
  lifecycle refs: `refs/heads/main` (edge), `refs/heads/stable` (default), and
  `refs/tags/vX.Y.Z` (exact org pins). It never publishes a mutable local
  branch name. A per-remote atomic push prevents a channel or pin from moving
  without the others. This is the PRINCIPAL RULE D4 repair for `R5-REV-002`
  extended to the release-channel contract.
- **Activate public CLI** resolves the newly published immutable tag back to the
  accepted commit, Git tree, and canonical content digest, materializes that
  generation under the synthesis-owned content-addressed release store, and
  atomically switches the managed `synthesis` launcher and active descriptor.
  This precedes native installation because new hooks depend on the verified
  launcher. The descriptor records installation prerequisites, not live loading.
- **Install** honors the saved desired client selection; an unconfigured
  maintainer machine retains the explicit Claude, Codex and Muse publisher
  targets. It uses each selected client's own commands, in the order each client
  requires. For Codex that means `plugin marketplace upgrade` **before**
  `plugin add`, because Codex installs *from* its git marketplace snapshot —
  skipping the upgrade installs the previous release while appearing to
  succeed. Before that destructive Codex refresh, the publisher snapshots every
  real versioned cache root retained by any client into a durable recovery archive.
  Immutable release tags supply authoritative tracked bytes. For releases that
  predate immutable tags, a peer-client or prior archive root is accepted only
  after its manifests, complete hook target set, and skill tree validate. Known
  Codex installation metadata is retained; arbitrary untracked cache files are
  not promoted into recovery state. The
  publisher holds a single-writer transition lock, restores missing Codex roots,
  repairs partial ones, and repeats the check until the tree has remained
  unchanged for ten seconds after the client command returned. That synchronous
  receipt covers the release transaction; it cannot prove that the client will
  not create another cache generation minutes later. The publisher therefore
  installs `cache_guardian.py` under the durable recovery root and verifies its
  user-level launchd or systemd supervisor before archive migration, then verifies
  recovery again before returning. The guardian shares
  the release lock, protects every archived version except the newest
  client-owned version, and rehydrates missing historical roots after any later
  cache replacement. It never deletes a cache path or overwrites differing
  existing content. Restoration runs newest-history-first so the immediately
  preceding version is available before older roots during a large recovery.
  The onboarding engine invokes the installed guardian synchronously after a
  Codex refresh and refuses to report success until the invoking task's exact
  version root and hook targets are present. That synchronous doctor waits up
  to 120 seconds for a guardian pass already holding the transition lock; the
  watcher and explicit one-shot mode stay nonblocking. The watcher continues
  protecting those roots against later reconciliation after either command
  exits.
  The deduplicated archive has a 512 MiB hard budget and never evicts a historical version
  automatically when that budget is reached; unverifiable cleanup fails the
  release closed. Transient verified migration copies are retired after the
  committed store contains their bytes and modes. Symlinked recovery roots and
  unsafe links are refused; client liveness markers are excluded.
- **Verify** is the point of the whole script, and it checks each selected client
  **twice**: what the CLI reports, and the plugin manifest at the path the CLI
  says it loads. The complete immutable inventory must match; extra loadable
  files and filesystem-type changes fail. Only the existing bounded client
  metadata and Python-cache policy is exempt. Stable-path selection uses a
  verified selected client, and the Codex guardian runs only when Codex is
  selected. User-selected desired state remains owned by `synthesis setup`
  and later reconciliation commands.
- **Reconcile lifecycle** binds repair to the exact published release digest and
  unchanged desired-state digest after native installation. Both bindings are
  rechecked under acquired lifecycle locks before any recovery mutation. The repair verifies
  each selected native root against the published source inventory, reconciles
  owned instruction provenance and commits a new generation only after engine
  doctor passes. It preserves the selected profile, clients, organization commit,
  personal sources and prior generations. Disabled, modular or conflicting pinned
  selections refuse before release mutation; absent desired state stays absent.
  A generation records installation, not a fabricated native reload receipt.

### Why a client's own version report is not sufficient evidence

A client can report the intended version while the tree it actually loads is
older — a stale marketplace snapshot, a partial install, or a hand-made cache
directory all produce that state, and a report-only check passes green through
every one of them. This was not hypothetical: it is the regression that
motivated the script, and `test_release.py` pins it as a test that must fail
when reported-version and on-disk-version disagree.

The general rule this encodes, worth applying beyond releases: **when a
verification asks a system to describe itself, verify the description against
the artifact.** A self-report is a claim, not evidence.

### Required autopilot check partitions

The release owner and CI run `release_check_groups.py` for `state`, `native`,
`evaluation`, and `core`. Each partition collects the entire autopilot directory,
rejects duplicate node IDs, and derives its domain membership. Newly collected
files enter the core group unless their name belongs to a declared domain rule;
no static test-file allowlist can silently exclude them. Collection errors,
missing or duplicate execution phases, failed tests, and unexpected skips fail
the release. The explicit macOS-only process-isolation control remains
inapplicable on non-macOS hosts; missing sandbox capability never becomes a pass.

Each check keeps the existing 900-second wall-time ceiling. The inner pytest
owner has 880 seconds, leaving cleanup and reporting reserve; four sequential
partitions admit at most four check windows, not an unbounded retry. A slow group
fails and requires measured redistribution or implementation correction.
The runner bounds capture to 8 MiB, the inventory report to 4 MiB, collection to
20,000 tests, and source fingerprinting to 128 MiB / 20,000 members / 30 seconds.
These generous finite ceilings are refusal boundaries, never truncation passes.
All required checks bind unchanged source bytes before and after execution and
between checks. Existing required environment (including a verified browser
executable) remains available; external pytest selection/plugin flags are removed at the common required-check
owner for both autopilot and all other required checks. Each check gets a fresh
private `PYTHONPYCACHEPREFIX`, with automatic bytecode writing disabled; stale
matching-header caches cannot substitute different executed source. Explicit
compilation checks still perform their requested compilation within that owned
temporary prefix. The owner removes its temporary cache only after child cleanup.

The required-check owner creates a separate process group, uses no inherited
stdin, and terminates that owned group on success, failure, timeout, output
overflow, or interruption. This confines cleanup to trusted repository checks;
it is not an OS isolation replacement and does not claim custody over processes
that deliberately escape their session. Executable consumer isolation stays
mandatory. Reports include each selected test phase and durations so slow groups
can be diagnosed without raising timeouts or dropping coverage.
