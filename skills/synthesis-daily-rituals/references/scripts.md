# The ritual scripts: command lines, output, exit codes

Read before running a script. `<rituals>` is this skill's folder; `<W>` is the workspace. Every
script is standard-library Python that runs on Apple's `/usr/bin/python3`; the YAML manifests are
read by `scripts/simple_yaml.py`, which refuses anything it cannot read rather than half-reading it.

| Command | What it prints | Exit |
|---|---|---|
| `python3 <rituals>/scripts/ritual_state.py record --direction day-start\|day-end\|weekly-review --workspace <W> --date YYYY-MM-DD [--mode quick] [--outcome clean] [--session ID] [--pointer FILE] [--count sent=3]` | `recorded day-end <W> <date> (<outcome>)` | 0; non-zero on an empty workspace, a missing or malformed date, an unknown outcome, mode `migration`, a record over 2,048 bytes, or a log whose last line was interrupted |
| `python3 <rituals>/scripts/ritual_state.py query summary\|last\|open [--workspace <W>] [--today D] [--json]` | one row per workspace (last close, streak, last weekly review, OWED) and every workday started and never closed | 0; non-zero on an empty workspace or unreadable config |
| `python3 <rituals>/scripts/ritual_state.py query weekly-review\|streak --workspace <W> [--json]` | `{"workspace", "last_weekly_review", "owed"}` or `{"workspace", "streak"}` | non-zero without `--workspace` when the log names more than one workspace (streak: always) |
| `python3 <rituals>/scripts/sync_watermark.py begin --workspace <W> --label day-start` | `run started <moment>` | 0 |
| `python3 <rituals>/scripts/sync_watermark.py window --workspace <W> --surface <s> [--target <id>]` | `<surface>: <from> → <to> (<span>)` then `oldest=<epoch> latest=<epoch>` | 0 |
| `python3 <rituals>/scripts/sync_watermark.py advance --workspace <W> --surface <s> --through <latest> [--target <id> ...] [--surface-level]` | JSON with each entry moved or refused | 2 when a watermark would move backwards, into the future, or surface-wide over per-target entries |
| `python3 <rituals>/scripts/sync_watermark.py defer --workspace <W> --surface <s> [--target <id>] --reason "<why>"` | JSON with the deferral | 2 without a reason |
| `python3 <rituals>/scripts/sync_watermark.py status --workspace <W> --surface <s> ... [--targets-from F] --since run` | a row per surface and per stale target, then the blocking keys | 1 while anything blocks; 2 on an empty declared set or no bound |
| `python3 <rituals>/scripts/repo_state.py --workspace-root ~/workspaces/<W> [--fetch] [--ff] [--skip <name>] [--json]` | one state per declared repo (CURRENT, CACHED, BEHIND, DECISION, DIRTY, BLIND, UNREACHABLE, EXCLUDED) with dirty files listed, then `N of M current, ...` | 2 any BLIND or UNREACHABLE; 1 any DECISION or DIRTY |
| `python3 <rituals>/scripts/repo_state.py --discover ~/workspaces[/<W>] [--fetch] [--ff]` | the same, for every repository two levels under the root (linked worktrees belong to their repository) | as above |
| `python3 <rituals>/scripts/decay_sweep.py --as-of YYYY-MM-DD --plans-dir <dir> [--plans-dir ...] [--artifacts-dir <dir>] --json` | JSON: `status` CLEAR, REVIEW or BLOCKED, the due items with source locators, every scanned and refused source | 2 BLOCKED; 0 otherwise (collection succeeded, nothing approved) |
| `python3 <rituals>/scripts/portfolio_review.py [--threshold 30] [--all] [--json] [--index P] [--source R]` | at most three stale "active" projects, oldest first, each with close / pause / pick up | 0 always |
| `python3 <rituals>/scripts/pr_queue_scan.py --workspace <W> [--json]` | review requests, own PRs and unreviewed PRs oldest first, and every repo not scanned with its reason | 0 always |
| `python3 <rituals>/scripts/mailboxes.py --manifest .agents/mailboxes.yaml --workspace <W> plan [--include-on-request <address>] [--json]` | each due account with transport, role and mailboxes | 0; 2 on a manifest it refuses |
| `python3 <rituals>/scripts/mailboxes.py --manifest .agents/mailboxes.yaml --workspace <W> report [--json]` | `mailboxes: N of M swept` and SWEPT, BLIND, UNREACHABLE or DEFERRED per account | 2 on any BLIND account or no open run |
| `python3 <rituals>/scripts/gchat_preflight.py --config .agents/gchat-sync.yaml --spaces <enumeration.txt> --json --out <declared.json>` | the resolved targets, `census: ...`, `enumeration: complete` or a BOUND line | 1 bounded or unresolved; 2 empty set or bad config |
| `python3 <rituals>/scripts/ritual_workers.py list\|coverage [--date D] [--json]` | the registry, or `coverage: <workspace> <run type> <finished> (<outcome>) · <workspace> pending · ...` | 2 on a registry it refuses |

## Files the scripts keep

- The ritual log, `<synthesis home>/rituals/history.jsonl`, and its optional `config.json`
  (`{"defaults": {...}, "workspaces": {"<W>": {"streak": "expected-days", "weekdays": [0,1,2,3,4],
  "non_working_dates": ["YYYY-MM-DD"]}}}`). `streak: expected-days` counts an unbroken run over
  days the workspace is expected to close; working on a day that is not expected credits the
  streak and never debits it; `none` (the default) is right for seats worked occasionally. A date
  in `non_working_dates` (holidays, time off) is never expected. The synthesis home is
  `~/.synthesis/v5` unless `SYNTHESIS_HOME` says otherwise; `RITUAL_STATE_DIR` or `--state-dir`
  points the tool at a copy to exercise.
- The watermark store, `<synthesis home>/sync-watermarks/<W>.json` ([sync-watermarks.md](sync-watermarks.md)).
- The workers registry, `~/.synthesis/ritual/workers.yaml` (or `RITUAL_WORKERS_FILE`), authored
  by the principal ([ritual-worker-contract.md](ritual-worker-contract.md)).

The SessionStart hook reads the same log through `synthesis/rituals.py` and adds one line to the
session's context: this workspace's last close, streak, workdays never closed, whether a day-start
is recorded today and whether the weekly review is owed, then the other workspaces as counts.
`rituals.py --owed-today` answers the 16:55 nudge; any failure makes the nudge fire.
