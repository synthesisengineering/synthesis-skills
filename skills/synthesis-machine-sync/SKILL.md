---
name: synthesis-machine-sync
description: "Move work between the principal's Macs and bring a Mac in or out: leave with synthesis handoff, arrive and resume, set up a new Mac, retire an old one. Use for: move work to another Mac, resume on another Mac, machine sync, bootstrap a new Mac, enroll a Mac, retire a Mac."
license: "Apache-2.0"
depends_on: ["synthesis-mac-sync", "synthesis-daily-rituals"]
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Machine Sync

Keep the principal's Macs working as one system. Work moves; processes do not. Git remotes
carry project records and code, the iCloud sync folder carries config and credentials
(`synthesis-mac-sync`), and everything else is per Mac: each Mac has its own board, its own
sessions and its own claims.

## Binding rules

1. **Clean install only.** Never copy one Mac's `~/.synthesis`, board session files, harness caches or transcript caches onto another; shared state arrives only through its remote or the sync folder.
2. **Leave only when nothing claimed is stranded:** `synthesis handoff` per project, then the strand scan. Dirty, unpushed or upstream-less work means the move is not done, and nothing reports it ready.
3. **Arrive without overwriting:** never pull over uncommitted changes; list them and decide with the principal first.
4. **Resume from the records alone:** project files, git and this Mac's board. No step depends on which harness (Claude Code, Codex, Muse) picks the work up.
5. **Secrets travel only through the sync folder's sensitive files** (`chmod 600`), never through git, a board message, a log or a prompt.
6. **Synced config stays `~`-rooted;** a literal `/Users/<name>/` path breaks on the other Mac. Consumers expand `~` and `$HOME` when they load.
7. **A new Mac is protected before its first commit:** setup, config pull, then `synthesis doctor` healthy. A fresh Mac is where a scanner once failed open.
8. **Judge a move by `git log` and `git status`,** never by the absence of an error line: a refused commit can print nothing that looks like failure.

## Contents

- **Procedure** (below): leave, arrive, a new Mac, retire a Mac. Read every time.
- `synthesis-mac-sync`'s [leaving-and-arriving.md](../synthesis-mac-sync/references/leaving-and-arriving.md): the same steps with the iCloud checks around them. Read when config also moved.
- [references/coverage-map.md](references/coverage-map.md): where every 1.0.0 rule lives now. [references/preserved.md](references/preserved.md): the retired fleet machinery and why, with the 1.0.0 SKILL.md verbatim. Read only to review the rewrite.

## Procedure

`<rituals>` is the synthesis-daily-rituals folder.

**Leave this Mac.**

1. In each session that holds a project's claims: `synthesis handoff -m "<generic message>"`. It commits and pushes only the records inside that session's claims and refuses, with the list, when any is dirty or unpushed.
2. Publish source work by explicit path under each repository's policy; fast-forward pushes only, no `--no-verify`, no force.
3. `python3 <rituals>/scripts/repo_state.py --discover ~/workspaces --fetch`. Resolve or name every DIRTY, DECISION, BLIND or UNREACHABLE repository.
4. If config changed, `brctl monitor --wait-uploaded -t 300 "$ICLOUD_BASE"` before writing the arrive note for the other Mac.
5. `synthesis release`.

**Arrive on a Mac.**

1. `brctl download "$ICLOUD_BASE"` and poll until no `.icloud` placeholder remains; pull config (`synthesis-mac-sync`).
2. `python3 <rituals>/scripts/repo_state.py --discover ~/workspaces --fetch --ff`: fast-forwards only clean branches that are strictly behind; lists uncommitted files and leaves them alone.
3. `synthesis brief <project>`: the phase and next action from the records, with a warning when the knowledge checkout is behind its fetched upstream or a newer copy exists elsewhere. Resolve the warning before working.
4. Board truth (`synthesis who`, `synthesis inbox`), then claim what this session will write: `synthesis claim <paths> --project <id> --goal "<goal>"`.

**A new Mac.**

1. `python3 <synthesis-onboarding>/scripts/setup.py`. It installs the plugin in each harness, the runtime, its hooks and the global git hooks, and clones the workspace repositories `repos.yaml` declares. Rerun it after any interruption; existing clones are fast-forwarded, and dirty or diverged ones are skipped and named.
2. Pull the synced config and credentials with `synthesis-mac-sync`, then install the private layer.
3. `synthesis doctor`; the first line must say healthy before the first commit.
4. Add the Mac to the machine inventory (`scutil --get LocalHostName`) in the sync folder's config file.

**Retire a Mac.**

1. Hand off or release every claim the Mac holds (the leave steps above).
2. Mark it retired in the machine inventory, with the date, and push or sync the change.
3. Re-point its scheduled jobs, launch agents and runner tokens to a live Mac.
4. Rotate every secret the retired Mac could read, then remove its local synthesis state.
