---
name: synthesis-repo-guard
description: "Finds work stranded on this Mac: repositories with uncommitted, unpushed or unpulled changes or a detached HEAD, in a read-only scan with a JSON report and a count-only alert. Use at day-end, before switching Macs, or when asked what is unsynced or what is left to commit."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "3.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Synthesis Repo Guard

Agents and tools change files all day, and work left uncommitted or unpushed on one Mac
is invisible from the other. This skill finds it: `scripts/repo_sync_check.py` scans
every repository under a workspace root and reports what is dirty, ahead, behind or
detached, without changing anything. Committing this session's own records is
`synthesis handoff`; the rules both follow are below.

## Binding rules

1. **Detection never modifies.** The scan reads; it never commits, stages, fetches or pushes.
2. **Alerts carry a count and a pointer, never a name.** Speech and banners never name a repository, workspace or client: speakers are overheard and banners are screen-shared, at all times, not only while sharing (2026-07-08). Detail goes only to pull channels the principal opens: the report file and synthesis-console.
3. **Quiet means quiet.** While `~/.synthesis/quiet-audio` exists, nothing speaks or shows a banner; the report still updates, so muting loses nothing.
4. **Only reads may run on a schedule.** Never schedule anything that commits or pushes: wall-clock mutation races repositories across machines.
5. **Commit only what this session changed,** inside its claims, by exact path, with every hook running: `synthesis handoff`. Never sweep another session's dirty files into a commit (2026-05-13), and read the result back from `git log`, not from the absence of an error.
6. **Never force.** Fetch, then push only as a fast-forward; on divergence keep the commit local and report it. Never rebase, force-push or `--no-verify`, and leave an `index.lock` alone.
7. **Never publish a private record to a remote outside the principal's own namespace,** whatever a path glob matched: one glob once matched a repository with a client remote.

## Contents

- **Procedure** (below): run the scan, read it, act on it.
- [references/scan.md](references/scan.md): the report file and its fields, the markers, exit codes, the synthesis-console contract, and scheduling. Read when wiring the scan into a ritual, the console or a hook.
- [references/handoff-rules.md](references/handoff-rules.md): the rules for committing records, with the incident behind each, and which of them `synthesis handoff` enforces. Read before committing records for a session or changing the handoff.
- [references/coverage-map.md](references/coverage-map.md): where every part of 2.7.3 lives now (ruling D8).
- [references/preserved.md](references/preserved.md): what was not kept and why, with the 2.7.3 text verbatim. Read only to review the cut.

## Procedure

1. **Scan:** `python3 <synthesis-repo-guard>/scripts/repo_sync_check.py` scans `~/workspaces` three levels deep (`--workspace DIR`, `--max-depth N`). It prints each repository that needs attention with its markers, then one count line:

   ```text
   /Users/you/workspaces/site/blog
     [uncommitted] 2 uncommitted file(s)
     [unpushed] 1 unpushed commit(s) on main
   1 of 24 repositories need attention.
   ```

   It writes `~/.synthesis/repo-guard/last-report.json` unless `--no-report`; `--json` prints the repositories that need attention as JSON; `--quiet` prints nothing. Exit 0 means all clean, 1 something needs attention, 2 an error (no workspace).
2. **Alert,** when a ritual or hook wants one: add `--alert` for a generic banner and spoken count, which honors the mute flag.
3. **Act:** for this session's own records, `synthesis handoff` (it says READY or NOT READY and why). For anything else, tell the principal what the scan found in the session, where only they read it, and leave the repository alone: another session or the principal owns that work. `synthesis who` shows which session claims a path.
4. **At day-end and before switching Macs,** run the scan after `synthesis handoff`; it is the final check that nothing is stranded.
