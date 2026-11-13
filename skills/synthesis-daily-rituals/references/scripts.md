# The ritual scripts: command lines, output, exit codes

Read before running a script. `<rituals>` is this skill's folder; `<W>` is the workspace. Every
script is standard-library Python that runs on Apple's `/usr/bin/python3`; the YAML manifests are
read by the plugin's one YAML reader, `synthesis/yamlish.py`, which refuses anything it cannot read rather
than half-reading it.

| Command | What it prints | Exit |
|---|---|---|
| `python3 <rituals>/scripts/ritual_state.py record --direction day-start\|day-end\|weekly-review --workspace <W> --date YYYY-MM-DD [--mode quick] [--outcome clean] [--session ID] [--pointer FILE] [--count sent=3] [--travel FILE]` | `recorded day-end <W> <date> (<outcome>)`, then `critical deadlines: N open, M within 7 days`, then, where the workspace checks travel, `travel: N in-person events through <day>, each with its travel`, then `choices: N open in today's plan, each with a recommendation` | 0; non-zero on an empty workspace, a missing or malformed date, an unknown outcome, mode `migration`, a record over 2,048 bytes, a log whose last line was interrupted, a critical deadline past due and open (each is named), an open choice in the day's plan with no recommendation or, where it commits the principal's time, no consequences (each is named), a travel result that is missing, for other days, at odds with itself or holding a flagged event, a clean outcome over plans that could not be read whole, or a workspace that declares no plan folders |
| `python3 <rituals>/scripts/ritual_state.py query summary\|last\|open [--workspace <W>] [--today D] [--json]` | one row per workspace (last close, streak, last weekly review, OWED) and every workday started and never closed | 0; non-zero on an empty workspace or unreadable config |
| `python3 <rituals>/scripts/ritual_state.py query weekly-review\|streak --workspace <W> [--json]` | `{"workspace", "last_weekly_review", "owed"}` or `{"workspace", "streak"}` | non-zero without `--workspace` when the log names more than one workspace (streak: always) |
| `python3 <rituals>/scripts/sync_watermark.py begin --workspace <W> --label day-start` | `run started <moment>` | 0 |
| `python3 <rituals>/scripts/sync_watermark.py window --workspace <W> --surface <s> [--target <id>]` | `<surface>: <from> → <to> (<span>)` then `oldest=<epoch> latest=<epoch>` | 0 |
| `python3 <rituals>/scripts/sync_watermark.py advance --workspace <W> --surface <s> --through <latest> [--target <id> ...] [--surface-level]` | JSON with each entry moved or refused | 2 when a watermark would move backwards, into the future, or surface-wide over per-target entries |
| `python3 <rituals>/scripts/sync_watermark.py defer --workspace <W> --surface <s> [--target <id>] --reason "<why>"` | JSON with the deferral | 2 without a reason |
| `python3 <rituals>/scripts/sync_watermark.py status --workspace <W> --surface <s> ... [--targets-from F] --since run` | a row per surface and per stale target, then the blocking keys | 1 while anything blocks; 2 on an empty declared set or no bound |
| `python3 <rituals>/scripts/repo_state.py --workspace-root ~/workspaces/<W> [--fetch] [--ff] [--skip <name>] [--json]` | one state per declared repo (CURRENT, CACHED, BEHIND, DECISION, DIRTY, BLIND, UNREACHABLE, EXCLUDED) with dirty files listed, then `N of M current, ...` | 2 any BLIND or UNREACHABLE; 1 any DECISION or DIRTY |
| `python3 <rituals>/scripts/repo_state.py --discover ~/workspaces[/<W>] [--fetch] [--ff]` | the same, for every repository two levels under the root (linked worktrees belong to their repository) | as above |
| `python3 <rituals>/scripts/decay_sweep.py --as-of YYYY-MM-DD --plans-dir <dir> [--plans-dir ...] [--artifacts-dir <dir>] [--records-dir <dir>] --json` | JSON: `status` CLEAR, REVIEW or BLOCKED, the due items with source locators, the `critical` view (`open`, `closed`, `unclassified`), every scanned and refused source | 2 BLOCKED; 0 otherwise (collection succeeded, nothing approved) |
| `python3 <rituals>/scripts/decay_sweep.py --as-of YYYY-MM-DD --workspace <W> --alert [--json]` | the same over the folders `<W>` declares, opening with `CRITICAL: N open (P past due, L within 7 days); A due an alert today` and one line per critical item; `--alert` posts one count-only banner and spoken line when any is due and reports it under `critical.alert` | 2 BLOCKED (including a workspace that declares no folders); 0 otherwise |
| `python3 <rituals>/scripts/decay_sweep.py --as-of YYYY-MM-DD --alert-declared` | `critical alert: N due across M declared set(s) of plan folders; {...}` after one alert for every workspace together (the 16:55 nudge runs this) | 0; 2 when the ritual config cannot be read |
| `python3 <rituals>/scripts/relied_on.py --workspace <W>\|--all [--timeout SECONDS] [--json]` | whatever is down first, one line each, `DOWN <what> (relied on by <who>): <why>`, the why being `exit N: <the first line the check printed>`, `no answer in N s` or `could not be run (<reason>)`; then `ok <what>` for each healthy one, then `N relied on, M down`. With nothing declared, the one line `nothing another person relies on is declared for <W>`. `--all` checks every workspace in the ritual config and names the workspace on each line (`DOWN <W>: <what> ...`). `--json` prints one object: `relied_on` (a row per entry with `workspace`, `what`, `by`, `ok` and `why`, whatever is down first), `down` and `nothing_declared`. Each check gets the timeout (20 seconds unless `--timeout` says otherwise), one after another, so give the command that long for each entry | 1 when anything is down or an entry cannot be run as written (it counts as down); 2 when nothing was checked, with one `NOT CHECKED: <why>` line on the error stream: the ritual config cannot be read or the workspace is not in it (`NOT CHECKED: <config file>: <why>`), the guards' config cannot be read or is not a JSON object, or the synthesis runtime cannot be imported; 0 otherwise. A run that never started, exited with any other code or printed none of the lines this row documents checked nothing: it is reported first, as not checked, and never read as healthy |
| `python3 <rituals>/scripts/portfolio_review.py [--threshold 30] [--all] [--json] [--index P] [--source R]` | at most three stale "active" projects, oldest first, each with close / pause / pick up | 0 always |
| `python3 <rituals>/scripts/stop_reprompts.py [--workspace W] [--since D] [--until D] [--json] [--archive P]` | the replies the Stop hook sent back in the window (default the last seven days), by check and harness, and any phrase or file named more than once | 0 always |
| `python3 <rituals>/scripts/stray_lessons.py --since YYYY-MM-DD --repo <knowledge repository> [--repo ...] [--json]` | each lesson heading or **Lesson:** line added to a project record since the date whose section links to no lessons folder, then any repository it could not read | 0 always |
| `python3 <rituals>/scripts/pr_queue_scan.py --workspace <W> [--json]` | review requests, own PRs and unreviewed PRs oldest first, and every repo not scanned with its reason | 0 always |
| `python3 <rituals>/scripts/mailboxes.py --manifest .agents/mailboxes.yaml --workspace <W> plan [--include-on-request <address>] [--json]` | each due account with transport, role and mailboxes | 0; 2 on a manifest it refuses |
| `python3 <rituals>/scripts/mailboxes.py --manifest .agents/mailboxes.yaml --workspace <W> report [--json]` | `mailboxes: N of M swept` and SWEPT, BLIND, UNREACHABLE or DEFERRED per account | 2 on any BLIND account or no open run |
| `python3 <rituals>/scripts/gchat_preflight.py --config .agents/gchat-sync.yaml --spaces <enumeration.txt> --page-size <N> --json --out <declared.json>` | the resolved targets, `census: ...`, `enumeration: complete` or a BOUND line; with `--json`, one object with `targets`, the same `census` and `enumeration` lines, `bound` and `declared` (what `--out` writes) | 1 bounded or unresolved; 2 empty set or bad config |
| `python3 <rituals>/scripts/linkedin_messages.py plan --config .agents/linkedin-sync.yaml` | per declared inbox (`focused`, `other`; both when none is declared), `open  <that inbox's address in the new-message view>` and `read  <inbox>: read through <day>; scroll back to that day, stop there, and pass --inbox <inbox> --since <day>`, or `never read; scroll back to <the day two weeks back>, ...` (`--today YYYY-MM-DD` sets the day it counts from) | 2 on a declaration it cannot use (no workspace, inboxes not a list, an inbox it has no address for) |
| `python3 <rituals>/scripts/linkedin_messages.py parse --text <saved list text> --read-at <ISO time> [--inbox NAME] [--since YYYY-MM-DD] [--opened N] [--empty] [--json]` | `LinkedIn messages, <inbox>: N conversations read from the list, back to <day>; K end with someone else (U unread, LinkedIn asks for a reply on G); none opened`, then a line naming any conversation the list marks as open (it is counted as opened), then one line per conversation that ends with someone else | 1 when the read stopped short of `--since` or an entry could not be read; 2 when the text holds no conversation list (and `--empty` was not passed) or shows a sign-in page or security check, or when `--empty` was passed over a text that holds conversations |
| `python3 <rituals>/scripts/ritual_workers.py list\|coverage [--date D] [--json]` | the registry, or `coverage: <workspace> <run type> <finished> (<outcome>) · <workspace> pending · ...` | 2 on a registry it refuses |

## Files the scripts keep

- The ritual log, `<synthesis home>/rituals/history.jsonl`, and its `config.json`
  (`{"defaults": {...}, "workspaces": {"<W>": {"streak": "expected-days", "weekdays": [0,1,2,3,4],
  "non_working_dates": ["YYYY-MM-DD"], "plans_dirs": ["<folder of dated plans>"],
  "artifacts_dirs": ["<folder of ritual-worker artifacts>"]}}}`; an example ships as
  `assets/ritual-config.example.json`). `plans_dirs` and `artifacts_dirs` declare where the
  workspace's dated plans live: the deadline sweep, `record` and the nudge read them, and `record`
  refuses a workspace that declares neither (`"plans_dirs": []` says it keeps none). `records_dirs` adds folders of
  other Markdown records (drafts, a ledger) whose items the sweep reads unless a plan carries them. A top-level
  `critical_words` list replaces the words that flag an untagged deadline as possibly critical
  ([critical-deadlines.md](critical-deadlines.md)). `streak: expected-days` counts an unbroken run over
  days the workspace is expected to close; working on a day that is not expected credits the
  streak and never debits it; `none` (the default) is right for seats worked occasionally. A date
  in `non_working_dates` (holidays, time off) is never expected. `quiet_after_days` (a whole
  number of days) marks a workspace worked occasionally, such as an advisory seat: it owes no
  weekly review, and once it has gone that many days without a ritual record, the session line
  counts it as quiet too long and the summary shows `QUIET <days> days`. Its declared mailboxes
  keep their own `sweep` cadence. `relied_on` lists what a person other than the principal relies
  on, each with the command that says whether it is healthy:
  `"relied_on": [{"what": "the intake form on the shared address", "by": "the sales team",
  "check": ["curl", "-fsS", "--max-time", "10", "https://intake.example.com/health"]}]`. `check` is
  a list of words, the program and then its arguments. No shell runs it, so nothing in it is
  expanded: name a program on the PATH or give its full path. The thing is healthy when the check
  exits 0 within the timeout. A check is a standing command, so the script puts each one to the
  guard first, as the shell command it is: one the guard would hold or refuse for an agent (a
  deploy, a send, a tunnel, a write to a protected folder) is reported as `DOWN ... could not be run
  (a guard holds it, as it would for an agent: ...)` and is never started. A check only looks: `curl`
  on a health address, a status command, a script that reads. The config is the person's own and
  outlives any one workspace, so word `what` and `by` as they can stay there (a role, not a name).
  `relied_on.py` runs every entry at each ritual, and an entry is added the day something is handed
  to another person to use. Declare it under the workspace it belongs
  to: an entry under `defaults` is checked for every workspace that declares none of its own. The
  synthesis home is
  `~/.synthesis/v5` unless `SYNTHESIS_HOME` says otherwise; `RITUAL_STATE_DIR` or `--state-dir`
  points the tool at a copy to exercise.
- The watermark store, `<synthesis home>/sync-watermarks/<W>.json` ([sync-watermarks.md](sync-watermarks.md)).
- The workers registry, `~/.synthesis/ritual/workers.yaml` (or `RITUAL_WORKERS_FILE`), authored
  by the principal ([ritual-worker-contract.md](ritual-worker-contract.md)).

The SessionStart hook reads the same log through `synthesis/rituals.py` and adds one line to the
session's context: this workspace's last close, streak, workdays never closed, whether a day-start
is recorded today and whether the weekly review is owed, then the other workspaces as counts.
`rituals.py --owed-today` answers the 16:55 nudge; any failure makes the nudge fire. The nudge
first runs `decay_sweep.py --alert-declared` from the runtime's copy of these scripts
(`<synthesis home>/current/skills/synthesis-daily-rituals/scripts/`), and shows a second fixed
banner when that check cannot run.
