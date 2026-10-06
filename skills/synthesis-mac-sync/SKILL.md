---
name: synthesis-mac-sync
description: "Keep several Macs in step: config files through iCloud, repositories and remotes through git, and work moved with synthesis handoff. Use for: mac sync, run my mac-sync, sync config, push or pull config to iCloud, sync repos, repo status, leaving this Mac."
license: "CC0-1.0"
depends_on: ["synthesis-daily-rituals"]
metadata:
  author: "Rajiv Pant"
  version: "3.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Synthesis Mac Sync

A methodology for keeping multiple Macs in sync using iCloud for configuration files and Git for
repositories, run end to end by the agent: the user says "run my mac-sync" and the agent does it
with as few approval prompts as possible. This skill is the protocol; the user's config file in
the iCloud sync folder is the specifics (which files, which machines, which repos). Moving work
from one Mac to another uses `synthesis handoff` and the steps in
[leaving-and-arriving.md](references/leaving-and-arriving.md), shared with `synthesis-machine-sync`.

## Binding rules

1. **Never overwrite with empty.** If either side is empty or missing, keep the non-empty one; copy the newer side automatically; prompt only when both changed and timestamps cannot decide.
2. **Verify iCloud propagation:** after every push wait for upload (`brctl monitor --wait-uploaded`); before every pull trigger downloads and poll until no `.icloud` placeholder remains. Never write a cross-Mac handoff before upload is confirmed; skipping this loses data.
3. **Git: fetch first, fast-forward only, never force-push,** and never pull over uncommitted changes: list them and ask. Skip repos mid-rebase or mid-merge and report them.
4. **Never bypass hooks** (`--no-verify`) without the user's explicit approval for that one commit. Commit messages stay generic: no people, companies, codenames, titles or topics, because git history is persistent.
5. **Honor `push_policy`:** `owner-only` repos push only to the owner's personal remotes, else abort and alert; `pr-required` repos never auto-push.
6. **Manifests are multi-machine documents:** merge, never regenerate from one Mac's scan. Never remove a repo entry, a remote or a local clone; a finished engagement goes `dormant` and stays on disk.
7. **Sync only the keys you own** in a client config the client also writes (Codex `config.toml`); never copy the whole file.
8. **Batch:** all files in one script, all repos in two or three. Dozens of approval prompts defeat the automation.
9. **Sensitive files get `chmod 600`;** quote every path (iCloud paths contain spaces). No secret value goes into any git repo, board message or log.
10. **Leave and arrive by the protocol:** `synthesis handoff` per project, then the strand scan; arriving, pull without overwriting local changes, then `synthesis brief`.
11. **Alerts carry counts and a pointer only,** never repo, workspace or client names, and honor `~/.synthesis/quiet-audio`.

## Contents

- **Procedure** (below): full, config-only and git-only sync, and the summary. Read every time.
- [references/icloud-config-sync.md](references/icloud-config-sync.md): configuration, setup, the one-script config sync, the Codex overlay, iCloud propagation checks, the config sync protocol and file format. Read before any config sync.
- [references/repo-sync.md](references/repo-sync.md): push policy, the batched git scripts, per-workspace `repos.yaml`, repo and remote sync protocols, the manifest merge protocol, automation policy, the summary format. Read before any git sync.
- [references/machines-and-symlinks.md](references/machines-and-symlinks.md): new-Mac bootstrap, machine inventory, one-time actions, workspace config symlinks. Read when setting up a Mac or reconciling symlinks.
- [references/leaving-and-arriving.md](references/leaving-and-arriving.md): moving work between Macs with `synthesis handoff`, the strand scan, the arrive steps. Read before changing Macs.
- [references/coverage-map.md](references/coverage-map.md): where every 2.1.0 rule lives now. [references/preserved.md](references/preserved.md): what was retired and why, and the 2.1.0 SKILL.md verbatim. Read only to review the rewrite.

## Procedure

**Full sync ("run my mac-sync"),** in this order:

1. **Pre-pull iCloud download check:** `brctl download "$ICLOUD_BASE"`, then poll for `.icloud` placeholders until none remain (five-minute timeout; alert on timeout).
2. **Config file sync,** bidirectional by modification time, in one bash call ([icloud-config-sync.md](references/icloud-config-sync.md)).
3. **Post-push iCloud upload check:** `brctl monitor --wait-uploaded -t 300 "$ICLOUD_BASE"`; do not report completion before it returns.
4. **Workspace config symlinks:** the idempotent reconciliation against each workspace-private repo's `.agents/` ([machines-and-symlinks.md](references/machines-and-symlinks.md)).
5. **Git repo sync:** fetch everything, pull what is behind and clean, push what is ahead and clean under `push_policy`, reconcile remotes from `repos.yaml`, and report the rest ([repo-sync.md](references/repo-sync.md)). The read-only view of every repo is `python3 <synthesis-daily-rituals>/scripts/repo_state.py --discover ~/workspaces --fetch` (one state per repo, uncommitted files listed, exit 2 for BLIND or UNREACHABLE, 1 for DIRTY or DECISION).
6. **One-time actions:** run the ones targeted at this Mac (`scutil --get LocalHostName`), mark them `[COMPLETED date]`.

**Config only:** "sync my Mac config files from iCloud" (pull) or "push my Mac config files to iCloud" (push), each with its propagation check.

**Git only:** "sync my repos with GitHub" (full) or "show me the status of my repos" (the strand scan without `--ff`).

**Leaving this Mac or arriving on another:** [leaving-and-arriving.md](references/leaving-and-arriving.md).

**Summary:** Actions Taken, then Needs Attention (uncommitted changes with a suggested generic commit message, diverged repos, conflicts, unexpected states: ask about each), then Informational (stashes, non-fast-forward pushes, repos without a remote, clean count). Prompt only for Needs Attention.
