# Leaving one Mac and arriving on another

Read before moving work to another Mac, and on the Mac that receives it. Same-Mac switching
between Claude Code, Codex and Muse needs none of this: on one Mac the files on disk are the
handoff, and nothing needs committing.

Contents: Leaving a Mac · Arriving on a Mac · What never moves between Macs · Why.

## Leaving a Mac

1. **Hand off every project worked on this Mac:** `synthesis handoff -m "<generic message>"` in
   the session that holds the project's claims. It commits and pushes only the records inside
   this session's claims and refuses, with the list, when a claimed record is dirty or unpushed;
   it never reports "ready" over them. Read its report.
2. **Publish source work** under each repository's policy: run its tests, commit only the paths
   inside this session's claims (another session may have staged files in the same index; commit
   by explicit path), and push. Never `--no-verify`, never force, never rebase on your own; on a
   remote that moved ahead, fetch and push only as a fast-forward, and on divergence leave the
   local commit and report it.
3. **Run the strand scan:** `python3 <synthesis-daily-rituals>/scripts/repo_state.py --discover ~/workspaces --fetch`.
   Every repository lands in one state; anything DIRTY, DECISION (ahead or diverged), BLIND (no
   upstream, detached) or UNREACHABLE is work that would stay behind on this Mac. Resolve each
   one, or name it to the principal, before calling the move done.
4. **Wait for iCloud upload** when config changed: `brctl monitor --wait-uploaded -t 300 "$ICLOUD_BASE"`
   ([icloud-config-sync.md](icloud-config-sync.md)). Do not write the arrive prompt for the other
   Mac until this returns.
5. **Release claims** (`synthesis release`) so nothing on this Mac holds work that has moved.

## Arriving on a Mac

1. **Materialize iCloud first:** `brctl download "$ICLOUD_BASE"` and poll until no `.icloud`
   placeholder remains, then pull config ([icloud-config-sync.md](icloud-config-sync.md)).
2. **Pull, never over uncommitted work:**
   `python3 <synthesis-daily-rituals>/scripts/repo_state.py --discover ~/workspaces --fetch --ff`.
   It fast-forwards only branches that are strictly behind and whose working tree is clean. A
   repository with uncommitted changes is listed file by file and left as it is: decide with the
   principal what those changes are before anything is pulled over them.
3. **Resume:** `synthesis brief <project>` (or `synthesis use <project>` first). It states the
   phase and next action from the records, and warns when the knowledge checkout is still behind
   its fetched upstream or a newer copy of the records exists elsewhere; resolve that warning
   before working.
4. **Claim** what this session will write (`synthesis claim <paths> --project <id> --goal "<goal>"`).

## What never moves between Macs

Never copy `~/.synthesis` subtrees, board session files, harness caches or transcript caches
between Macs. Per-machine state stays per-machine; shared state arrives only through its git
remote or the iCloud sync folder. Claims are per Mac: a session on the other Mac does not hold
this Mac's areas.

## Why

Work moved between Macs with unpushed or unpulled state (design 2026-09-19, acceptance cases
FLEET-AC-09 to 11): the source must refuse while anything claimed is dirty, unpushed or has no
upstream, and the destination must refuse to pull over its own uncommitted files. Judge a
commit by `git log` and `git status`, never by the absence of an error line: a refused commit
can print nothing that looks like failure.
