# Releasing the public plugin (v5)

## Contents

- [Why release is a script](#why-release-is-a-script)
- [The procedure](#the-procedure)
- [What the script refuses, and why](#what-the-script-refuses-and-why)
- [Each harness's own commands](#each-harnesss-own-commands)
- [Why a client's own version report is not sufficient evidence](#why-a-clients-own-version-report-is-not-sufficient-evidence)
- [The release train: one publisher at a time](#the-release-train-one-publisher-at-a-time)
- [The stable path: never pin a version](#the-stable-path-never-pin-a-version)
- [The merge gate: branch protection and auto-merge](#the-merge-gate-branch-protection-and-auto-merge)
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
- another live session holds the release train;
- the five collections, built from HEAD's commit, fail a check, or the collections file
  cannot be read ([collections.md](collections.md)); a dry run builds and checks them too.

Publication pushes `main`, `stable`, the tag and the collections to every push remote,
one atomic push per remote, so a channel or pin never moves without the others. The
collections go as the `collections` branch: a commit whose tree is the five built
folders and their two marketplace files, on top of that remote's head of the branch, so
no release rewrites it; a run again reuses a head that already holds the same tree.
Success is read back with `git ls-remote`, never from an exit status: a piped push once
reported success while nothing moved (lesson 2026-09-21, release train quiet tree and
exit codes).

Then the GitHub release: for each GitHub remote, the script creates the release for the
tag (`gh release create --verify-tag --latest`, titled "Synthesis X.Y.Z", its notes the
version's CHANGELOG entry) unless it exists, and reads `gh release list` back until that
tag is the latest. A visitor reads GitHub's release list as the current version; before
5.3.9 v5 releases created none, and the list showed a 4.x release as latest.

Then the Homebrew formula, for the canonical repository only (a fork's release leaves it
alone). The script reads `Formula/synthesis.rb` on the tap's `main`, downloads the tag's
archive with `curl` and computes its sha256 as Homebrew will, and, unless `main` already
serves that archive, opens a pull request on the tap from a `synthesis-X.Y.Z` branch that
sets the formula's `url` and `sha256`, then sets it to merge when its checks pass (`gh pr
merge --auto`). The tap's own checks install and test every formula, so a formula that
cannot install never merges. A rerun reuses the open pull request. The pull request goes
up before the harnesses install, so its checks run meanwhile; after `synthesis doctor`
the script waits up to 30 minutes for the merge and reads the formula back from `main`.
Failed checks, a closed pull request, no merge in time, or a `main` that does not serve
the tag leave the release not complete. From 5.0.3 to 5.3.11 no release moved the
formula, so `brew install synthesisengineering/tap/synthesis` installed 5.0.3's
onboarding, without the prerequisite checks and `--dry-run` that 5.3.3 added. The
formula is part of what a release publishes, so the approval to release covers the tap's
merge. The tap deletes each merged pull request's branch itself (its `delete_branch_on_merge`
setting, on since 2026-11-05; set it once with `gh api -X PATCH repos/OWNER/homebrew-tap -F
delete_branch_on_merge=true`). Once the merge is read back, the script deletes its own branch
if the tap has not, and reports one it cannot delete, which fails nothing.

GitHub's API sometimes answers with a server error (HTTP 5xx, or an empty error body that
`gh` reports as "unexpected end of JSON input"), sometimes after doing what was asked. A
stage that fails that way runs again, up to three times, 20 and then 40 seconds apart, and
the CI read in preflight does the same. Each stage reads what is already published before it
acts, so a second run finishes the first one's work: a release GitHub created while
answering 502 is found and not created twice, and a pull request it did not open is opened.
Any other error stops the release at once. On 2026-11-05 GitHub answered 502 to the
release's GitHub release and to its tap pull request, and the release took three runs by
hand.

A tap check whose jobs GitHub never gave a runner (each failed job cancelled before any
step ran, so the summary `ci` check failed) is run again, up to three times, and the
script keeps waiting for the merge; a check whose run is already running again is waited
for. A job that failed in its steps stops the release at once. On 2026-11-05 GitHub's
macOS runners turned away a job on `main`, on a pull request and on the tap within one
day, and the tap's stopped that day's release.

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

Codex also ties an approval to a fingerprint of the installed plugin's files (Codex
0.166), and every release changes them, so after each release Codex runs none of
synthesis's hooks, the guards included, until the person approves them again in
`/hooks`. Doctor fingerprints the installed plugin the way Codex does and fails until
then. The release still completes and prints each such approval as waiting on the
person, since no release can give it. Before 5.3.15 doctor compared only the hook
definitions and reported the hooks trusted while Codex ran none of them (2026-11-05).

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
frees it. A session quiet for eight hours is stale, and its claims with it:
`synthesis who --all` lists it marked `STALE` with its claims, and plain `synthesis who`
leaves it out unless it holds a live wait, when its row says `STALE` and
`waiting until HH:MM`. Taking a stale claim over (`synthesis claim --take`) is the
principal's call.

## The stable path: never pin a version

Instruction files and long-lived sessions that pin a versioned cache path
(`…/synthesis-skills/4.59.0/…`) go stale on the next release — on 2026-09-01
a session on a months-old engine read the shared coordination board as
corrupt, and a workspace's own day-start commands pinned a release twenty
versions behind. Hooks that named a harness-owned version folder broke a running Codex
task when a Codex update deleted that folder (2026-09-02, CHANGELOG 4.90.2).

v5 has two stable paths, both outside the harnesses' caches:

- `~/.synthesis/v5/bin/synthesis-hook` is what every hook calls. Its text never changes
  between releases, so a deleted plugin folder never breaks a running task. A hook
  approval is another matter: Muse has kept its approval across every release so far,
  and Codex asks again after each one, because it ties the approval to a fingerprint of
  the installed plugin. Until the person approves in `/hooks`, Codex runs none of the
  hooks; `release.py` names that approval as waiting.
- `~/.synthesis/v5/current` is the runtime. At each session start the hook passes the
  plugin folder the harness loaded; if it is a newer release, it is installed beside the
  old one and `current` switches atomically, and a session on an older plugin never
  switches it back. `release.py` installs from a verified install whatever its version,
  and `synthesis doctor` fails when `current` is missing or its files changed.

Instruction files and scripts call `synthesis` (or `~/.synthesis/v5/bin/synthesis`),
never a versioned folder.

## The merge gate: branch protection and auto-merge

"Merge only after CI passes" written as a rule is a convention any session can break by accident; the repository
enforces it instead. The CI workflow ends with one job, `ci`, that depends on every test job and passes only when all
of them passed; it runs even when one fails, so it never leaves a pull request waiting. Branch protection on `main`
and `stable` requires that one check, for admins too, since agents act with the maintainer's rights. Requiring the
summary job, not each matrix job by name, keeps the protection valid when the matrix changes. With auto-merge allowed,
`gh pr merge --auto --merge` merges a pull request the moment its checks pass, and a watcher on `main` releases it.
The release script is unaffected: it pushes `main` at the commit already there, and `stable` to a commit whose `ci`
check passed. A branch need not be current with `main` before it merges (`strict` off): `main`'s own CI on the merge
commit gates the release.

Set it once for each repository whose `main` reaches users:

```bash
gh api -X PATCH repos/OWNER/REPO -F allow_auto_merge=true
gh api -X PUT repos/OWNER/REPO/branches/main/protection --input protection.json
```

with `protection.json` holding `{"required_status_checks": {"strict": false, "contexts": ["ci"]}, "enforce_admins":
true, "required_pull_request_reviews": null, "restrictions": null}`, and the same for `stable`.

## After the release

- Read the doctor output the script prints. Codex `hook trust` and Muse `hook approval`
  failures need the person's approval (in Codex, after every release); the script
  prints them as waiting on your approval. Say so plainly.
- Tell the person which harnesses to restart: a restart reloads hooks and skills
  without a new conversation (lesson 2026-08-17).
