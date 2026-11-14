# The stranded-work scan

`scripts/repo_sync_check.py`: Python standard library and the git CLI, read-only.

## Contents

- [What the detector reports](#what-the-detector-reports)
- [The report file](#the-report-file)
- [Exit codes and options](#exit-codes-and-options)
- [Alerts](#alerts)
- [synthesis-console](#synthesis-console)
- [Scheduled execution — read-only only](#scheduled-execution--read-only-only)

## What the detector reports

| Condition | Marker |
|-----------|--------|
| Uncommitted changes (modified/staged/untracked) | `[uncommitted]` + file list |
| Unpushed commits | `[unpushed]` + count |
| Unpulled commits | `[behind]` + count |
| Detached HEAD | `[detached]` |
| Git errors | `[error]` |

Discovery walks the workspace root to `--max-depth` (default 3), skips folders starting
with a dot, and never descends into a repository's own folders. Up to eight repositories
are checked at once. Each check runs `git status --porcelain`, `git branch --show-current`
and `git rev-list --left-right --count origin/<branch>...<branch>`, with optional locks
off and lazy fetches disabled, and nothing else. Status lines are kept whole: their
first column carries meaning. A clean detached checkout is noted but does not count as
needing attention, since it strands nothing; a repository with no upstream reports only
its uncommitted files.

## The report file

`~/.synthesis/repo-guard/last-report.json`, rewritten on every run unless `--no-report`:

```json
{
  "generated_at": "2026-10-05T18:00:00-0400",
  "host": "machine-name",
  "total_repos": 24,
  "dirty_count": 1,
  "repos": [
    {"name": "blog", "path": "/Users/you/workspaces/site/blog", "clean": false,
     "issues": [
       {"type": "uncommitted", "detail": "2 uncommitted file(s)", "files": [" M a.md", "?? b.md"], "total": 2},
       {"type": "unpushed", "detail": "1 unpushed commit(s) on main", "count": 1}]}
  ]
}
```

`type` is one of `uncommitted`, `unpushed`, `behind`, `detached`, `error`. `files` holds at
most ten status lines; `total` counts them all. Names and file lists are fine here: the
file lives on the private disk and is rendered only by surfaces the principal deliberately
opens. 2.x also wrote `last-report.txt` and an append-only `history.jsonl`; neither had a
reader, and v5 keeps no per-run state that only grows.

## Exit codes and options

| Code | Meaning |
|------|---------|
| 0 | all clean & synced |
| 1 | repos need attention |
| 2 | error |

`--workspace DIR` (default `~/workspaces`), `--max-depth N` (default 3), `--json`,
`--quiet`, `--alert`, `--no-report`.

## Alerts

`--alert` posts a banner and speaks one sentence, both generic: `N repositories need
attention. Details are in your synthesis console.` It never names a repository,
workspace or client, and stays silent while `~/.synthesis/quiet-audio` exists (the
synthesis-console header button creates and removes that file; `touch`/`rm` works too).

Alerting humans about machine-fixable problems trains them to ignore alerts. Use
`--alert` where a person must act (day-end, before a machine switch), not on every
session end.

## synthesis-console

The console's sync tile reads `last-report.json` (`generated_at`, `dirty_count`, `repos`)
and refreshes it by running the scan with `--quiet` when the report is older than five
minutes: read-only and lid-safe. Its "Sync now" button and its producer receipts called
2.x's `checkpoint_sync.py`, which v5 removed; they need `synthesis handoff` (a cutover
change in synthesis-console, listed in the v5 cutover runbook).

## Scheduled execution — read-only only

If a tool supports no hooks at all, a scheduled **detector** run (`repo_sync_check.py --quiet`, reports only, no audio flags) is acceptable — it's read-only and interruption-safe. Do **not** schedule anything that commits or pushes: mutation stays event-driven. The console tile's polling normally makes scheduled detection unnecessary.
