# Releasing the public plugin (v5)

## Contents

- [Why release is a script](#why-release-is-a-script)
- [The procedure](#the-procedure)
- [What the script refuses, and why](#what-the-script-refuses-and-why)
- [Each harness's own commands](#each-harnesss-own-commands)
- [Why a client's own version report is not sufficient evidence](#why-a-clients-own-version-report-is-not-sufficient-evidence)
- [The release train: one publisher at a time](#the-release-train-one-publisher-at-a-time)
- [The stable path: never pin a version](#the-stable-path-never-pin-a-version)
- [After the release](#after-the-release)

## Why release is a script

`scripts/release.py` exists because the release sequence has exactly one failure mode
that matters and it is silent: the repository is the plugin (the marketplace manifests
carry no version and point at `./`), so pushing IS publishing — but each client keeps a
**version-pinned installation that does not follow the remote**. A
pushed-but-uninstalled release leaves the running clients behind their own source with
nothing visibly wrong. Muse rotted that way for weeks because nothing reinstalled it
(lesson 2026-09-18, unverified client installs rot silently).

v5 keeps only what that needs: preflight, the release train, publication, installation
with each harness's own commands, and byte verification. PR CI is the only test gate;
the script does not rerun the suite.

## The procedure

1. **Claim the train before authoring the version bump:**
   `synthesis claim <main checkout>/CHANGELOG.md --goal "release vX.Y.Z"`.
2. In a pull request, bump `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`
   and `.muse-plugin/plugin.json` together and add the CHANGELOG entry for that
   version. Merge once CI passes.
3. From a clean checkout of the merged default branch:

   ```bash
   python3 skills/synthesis-skills-manager/scripts/release.py --dry-run
   python3 skills/synthesis-skills-manager/scripts/release.py
   ```

   It prints one line per stage, then `release complete: vX.Y.Z` (exit 0) or
   `release NOT complete: vX.Y.Z` (exit 1), and runs `synthesis doctor` at the end.
4. A harness line reading `NOT verified` names each missing, differing or extra file.
   Fix the cause and rerun; `--install-only` reinstalls and re-verifies the tag that
   HEAD carries without publishing again (also the command for a new Mac).
5. On success the script releases the train claim. On failure the claim stays with
   this session, on purpose: the next attempt is still this session's.

## What the script refuses, and why

Before anything is pushed it refuses when:

- the repository root is an installed plugin copy (a harness cache or Muse bundle), not
  a source checkout;
- the tree has uncommitted changes, or HEAD is not on the default branch;
- the three plugin manifests disagree or lack a version;
- the CHANGELOG's newest entry is not that version;
- the version's tag already names another commit;
- CI has not passed for HEAD (read with `gh run list --commit`; unknown is not passed);
- another live session holds the release train.

Publication pushes `main`, `stable` and the tag to every push remote, one atomic push
per remote, so a channel or pin never moves without the others. Success is read back
with `git ls-remote`, never from an exit status: a piped push once reported success
while nothing moved (lesson 2026-09-21, release train quiet tree and exit codes).

## Each harness's own commands

Installation calls onboarding's `scripts/setup.py`, so release and setup cannot drift:

- **Claude Code:** `claude plugin marketplace update synthesis-engineering`, then
  `claude plugin update synthesis-skills@synthesis-engineering`.
- **Codex:** `codex plugin marketplace upgrade synthesis-engineering` **before**
  `codex plugin add synthesis-skills@synthesis-engineering`, because Codex installs
  *from* its git marketplace snapshot — skipping the upgrade installs the previous
  release while appearing to succeed.
- **Muse:** the tag is exported into the local bundle Muse installed from (its recorded
  path must be absolute), then `muse plugins update synthesis-skills`. A first install
  uses `muse plugins install <bundle>`; Muse refuses a second install from another path.

A harness that is not on the Mac is skipped, not failed. Codex hook trust and Muse hook
approval stay the person's decisions: when a hook definition changed, doctor names
what to approve in Codex's `/hooks` and with `muse plugins approve synthesis-skills`.

## Why a client's own version report is not sufficient evidence

A client can report the intended version while the tree it actually loads is
older — a stale marketplace snapshot, a partial install, or a hand-made cache
directory all produce that state, and a report-only check passes green through
every one of them. This was not hypothetical: it is the regression that
motivated the script, and on 2026-08-24 a skill edited without a version bump left
`plugin update` a no-op while both clients reported current and one loaded stale files.

The general rule this encodes, worth applying beyond releases: **when a
verification asks a system to describe itself, verify the description against
the artifact.** A self-report is a claim, not evidence.

So the script compares every file tracked at the tag with the file in the folder each
harness reports loading, byte for byte (a missing file, a different file, or an extra
file a harness would load all fail), and also requires the reported version to match.

## The release train: one publisher at a time

On 2026-09-01, two agent sessions releasing this repository in parallel
overtook each other five times — each merge to `main` turned the other's open
PR CONFLICTING with checks never run — and once both authored the same
version number. Coordination-board messages failed as a serializer because
an autonomous session mid-transaction does not re-read the board between
authoring a version and merging.

Serialization is mechanical. In v5 the train is a board claim on the main checkout's
`CHANGELOG.md` (the main checkout's, so two worktrees of the repository collide on the
same path). The board's claim-overlap refusal is the mutual exclusion, and
`release.py` takes the claim itself, refusing with the holder's session id and goal
when another live session has it. Claim it before authoring the version bump, hold it
through merge and release, and let the script release it on success. A crashed holder
blocks the train by design; the user — never another agent on its own initiative —
frees it. A claim with no activity for eight hours shows as stale in `synthesis who`;
taking it over (`synthesis claim --take`) is the principal's call.

## The stable path: never pin a version

Instruction files and long-lived sessions that pin a versioned cache path
(`…/synthesis-skills/4.59.0/…`) go stale on the next release — on 2026-09-01
a session on a months-old engine read the shared coordination board as
corrupt, and a workspace's own day-start commands pinned a release twenty
versions behind. Hooks that named a harness-owned version folder broke a running Codex
task when a Codex update deleted that folder (2026-09-02, CHANGELOG 4.90.2).

v5 has two stable paths, both outside the harnesses' caches:

- `~/.synthesis/v5/bin/synthesis-hook` is what every hook calls. Its text never changes
  between releases, so a harness's hook approval survives upgrades and a deleted
  plugin folder never breaks a running task.
- `~/.synthesis/v5/current` is the runtime. At each session start the hook passes the
  plugin folder the harness loaded; if its code differs, it is installed beside the old
  one and `current` switches atomically. `release.py` does the same from a verified
  install, and `synthesis doctor` fails when `current` is missing or its files changed.

Instruction files and scripts call `synthesis` (or `~/.synthesis/v5/bin/synthesis`),
never a versioned folder.

## After the release

- Read the doctor output the script prints. Codex `hook trust` and Muse `hook approval`
  failures need the person's approval of the changed hook definitions; say so plainly.
- Tell the person which harnesses to restart: a restart reloads hooks and skills
  without a new conversation (lesson 2026-08-17).
