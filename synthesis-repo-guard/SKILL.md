---
name: synthesis-repo-guard
description: "Workspace git-sync guard: detects uncommitted/unpushed repos, reports through confidentiality-safe channels (generic audio/banner + detailed report files + synthesis-console tile), and auto-heals private context repos at workflow events via checkpoint_sync.py. Works with any AI coding tool (Claude Code, Codex, Cursor, etc.) or standalone. Use when asked to: repo guard, check repos, session end check, sync check, repo status, workspace status, checkpoint sync, auto-commit context repos."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Repo Guard

## The Problem

AI coding assistants and project-management tooling create and modify files continuously. When a session ends — completion, timeout, closed window — uncommitted or unpushed changes are stranded on that machine, breaking the multi-machine sync chain. Tools that write files *outside* agent sessions (a project console writing status markers, manual edits) never commit at all.

v1 of this skill detected stranded state and alerted with a count ("N repositories have unsynced changes"). Two failures emerged in practice:

1. **The alert was unactionable — and leaky if made actionable.** A count says nothing useful; speaking repo names would fix that, but repo/workspace names are often client names, and audio reaches whoever is nearby or on an unmuted call. Notification banners leak the same way during screen-shares.
2. **The alert fired on machine-fixable states.** Most unsynced state is exactly what automation should heal at the next sensible checkpoint. Alerting humans about machine-fixable problems trains them to ignore alerts.

## The Architecture — three layers

| Layer | Component | Job |
|-------|-----------|-----|
| Detector | `repo_sync_check.py` (scan) | Find dirty / ahead / behind / detached repos under a workspace root |
| Messenger | `repo_sync_check.py` (output) | Generic audio/banner ping + detailed report files + console tile data |
| Remediator | `checkpoint_sync.py` | Auto-commit + push the configured private context-repo class at workflow events |

End state: routine changes are checkpointed silently, an always-on synthesis-console tile shows ambient status, and audible/banner alerts fire only for states automation cannot heal (blocked pre-commit hook, divergence, out-of-class dirt, stale lock) — rare, and always actionable.

## Confidentiality rule for alert surfaces (ABSOLUTE)

**Audio (`say`, alert sounds) and macOS notification banners never carry repo names, workspace names, or client names — only counts and a pointer ("details are in your synthesis console").** This holds at all times, not only while screen-sharing: presence detection is unreliable, and one leak outweighs the convenience. Identifying detail belongs exclusively in pull channels the user deliberately opens:

- `~/.synthesis/repo-guard/last-report.txt` / `last-report.json` / `history.jsonl` — written on every scan
- `~/.synthesis/repo-guard/checkpoint-state.json` — written on every checkpoint run
- the synthesis-console sync tile / page, which renders both

**Mute toggle:** all audible output (speech AND alert sounds) is suppressed while `~/.synthesis/quiet-audio` exists. synthesis-console exposes this as a header button; `touch`/`rm` the file works too. Muting loses nothing — reports and tile stay current.

## Detection vs. commit — scoping rules

`repo_sync_check.py` **detects and never modifies** — correct scope: every repo in the workspace.

Commits happen in exactly two sanctioned ways:

1. **Per-invocation agent commits** (unchanged rule): an agent commits only the files IT modified in the current invocation — never workspace-wide, never other sessions' work. See `synthesis-daily-rituals` "Commit Protocol".
2. **`checkpoint_sync.py`** — the deliberate, narrowly-scoped exception: it auto-commits repos in the configured **auto-sync class only** (private, single-writer context repos whose history is an operational log), protected by a runtime guard (below). Source-code repos and shared/public repos are structurally out of reach.

## The remediator: event-driven, never scheduled

`checkpoint_sync.py` runs ONLY at workflow events — moments when the user is demonstrably present and the machine awake:

- **AI-tool turn/session end** (throttled via stamp file, default 10 min): catches agent sessions — and manual edits too, since sessions are usually live.
- **After a console cockpit write:** the console calls `checkpoint_sync.py --repo <written-file> --now`, so producers own their commits through the one shared mechanism.
- **Rituals / mac-sync:** the existing day-boundary sweeps.

**Deliberately NOT a launchd/cron job.** Wall-clock daemons run detached from presence: they race the same repos across machines and create close-the-lid anxiety. Event-driven runs execute on the origin machine seconds after the change — which also shrinks multi-machine divergence windows, because work is pushed before you switch machines. (Read-only polling — the console tile refreshing — is exempt: interrupting a read is harmless.)

### The auto-sync class + runtime guard

Config `~/.synthesis/checkpoint-sync.yaml` (copy `checkpoint-sync.example.yaml`) lists the class by explicit path and glob. Membership criteria: private, single-writer knowledge/context repos (personal ai-knowledge repos, `*-<person>-private` workspace repos, daily plans). Never source-code repos, never shared/public repos.

**The runtime remote guard is independent of config:** a repo is touched only if EVERY push remote starts with an allowed prefix (your private GitHub namespace). A glob that accidentally matches a repo with a client/org remote is excluded at run time, every time — config declares intent; the guard verifies reality. Empty `allowed_remote_prefixes` fails closed.

### Safety properties

- Ordering: `add -A` → `commit` → `fetch` → push **only if fast-forward**.
- Distinct commit author (e.g. "Synthesis Checkpoint") — automated checkpoints are always distinguishable from curated commits.
- Divergence → the commit stays local (durable, resolvable) + alert. Never rebase, never force-push.
- Pre-commit hooks run normally; a rejection aborts that repo with an alert. **Never `--no-verify`.**
- Quiescence: skip repos with files modified in the last N minutes (default 15) — no mid-thought commits. `--now` bypasses this for producer writes that are known-complete.
- Stale `index.lock` (>10 min): reported, never deleted.
- Interruption-safe by construction: runs at interactive moments; an interrupted git op doesn't corrupt a repo (killed pushes are retryable; sleep suspends rather than kills).

---

## Quick Start

```bash
# Scan ~/workspaces, write reports, print text summary
./repo_sync_check.py

# Machine-readable scan (console tile source)
./repo_sync_check.py --json --quiet

# Generic attention ping if dirty (mute-aware)
./repo_sync_check.py --speak --notify --dirty-only

# What would the checkpoint do right now?
./checkpoint_sync.py --dry-run

# Throttled sweep (what the turn-end hook runs)
./checkpoint_sync.py --hook --quiet --notify

# Producer mode: checkpoint the repo containing a just-written file
./checkpoint_sync.py --repo ~/workspaces/example/daily-plans/today.md --now
```

### Exit codes (both scripts)

| Code | repo_sync_check.py | checkpoint_sync.py |
|------|--------------------|--------------------|
| 0 | all clean & synced | nothing needed / all healed |
| 1 | repos need attention | alerts raised (detail in state file) |
| 2 | error | error |

### What the detector reports

| Condition | Marker |
|-----------|--------|
| Uncommitted changes (modified/staged/untracked) | `[dirty]` + file list + fix hint |
| Unpushed commits | `[ahead]` + count |
| Unpulled commits | `[behind]` + count |
| Detached HEAD | `[detached]` |
| Git errors | `[error]` |

---

## AI Tool Integration

### Claude Code (`~/.claude/settings.json`)

Turn-end remediation (throttled — cheap no-op most turns) plus optional session-end verification:

```json
{
  "hooks": {
    "Stop": [
      { "hooks": [ { "type": "command",
        "command": "python3 ~/.claude/skills/synthesis-repo-guard/checkpoint_sync.py --hook --quiet --notify",
        "timeout": 120 } ] }
    ],
    "SessionEnd": [
      { "hooks": [ { "type": "command",
        "command": "python3 ~/.claude/skills/synthesis-repo-guard/repo_sync_check.py --dirty-only --speak --notify",
        "timeout": 60 } ] }
    ]
  }
}
```

### OpenAI Codex (`~/.codex/hooks.json`, with `codex_hooks = true`)

```json
{ "hooks": { "Stop": [ { "hooks": [ { "type": "command",
  "command": "python3 ~/.codex/skills/synthesis-repo-guard/checkpoint_sync.py --hook --quiet --notify",
  "timeout": 120 } ] } ] } }
```

The throttle stamp is shared across tools — multiple agents coexist without duplicate runs.

### Cursor (`.cursor/settings.json`)

```json
{ "task.onEnd": "python3 /path/to/checkpoint_sync.py --hook --quiet --notify" }
```

### synthesis-console (command center)

- **Always-on sync tile:** polls `repo_sync_check.py --json --quiet` (read-only; lid-safe) and renders `checkpoint-state.json` outcomes.
- **Quiet-audio toggle button:** creates/removes `~/.synthesis/quiet-audio`.
- **"Sync now" button:** `checkpoint_sync.py --no-throttle` (throttle bypassed; quiescence still honored).
- **Producer commits:** after writing a plan marker, the console fires `checkpoint_sync.py --repo <file> --now`.

### Scheduled execution — read-only only

If a tool supports no hooks at all, a scheduled **detector** run (`repo_sync_check.py --quiet`, reports only, no audio flags) is acceptable — it's read-only and interruption-safe. Do **not** schedule `checkpoint_sync.py`: mutation stays event-driven (see design rationale above). The console tile's polling normally makes scheduled detection unnecessary.

---

## Relationship to Other Skills

- **synthesis-mac-sync** — the full multi-machine sync operation (config files, credentials, all repos, with user approval). Repo-guard keeps context repos continuously clean so mac-sync's day-boundary sweep mostly finds nothing; run mac-sync when the report shows out-of-class problems or when switching machines.
- **synthesis-context-lifecycle / synthesis-daily-rituals** — those skills commit their own changes at the point of modification (the primary mechanism). checkpoint_sync is the safety net beneath them; `repo_sync_check.py` is the final verification gate at day-end.

---

## Command Reference

```
repo_sync_check.py [--workspace W] [--max-depth N] [--quiet] [--json]
                   [--dirty-only] [--alert] [--speak] [--notify]
                   [--report-dir D] [--no-report]

checkpoint_sync.py [--config C] [--repo PATH] [--hook] [--now]
                   [--no-throttle] [--dry-run] [--quiet] [--json]
                   [--speak] [--notify]
```

- `--speak/--notify/--alert` are generic + mute-aware on both scripts.
- `checkpoint_sync --repo` accepts any path inside a repo (resolved via `git rev-parse --show-toplevel`).
- `--hook` honors the shared throttle; `--now` bypasses throttle + quiescence (producer mode); `--no-throttle` bypasses throttle only (manual button).

---

## Design Principles

1. **Zero AI and zero external dependencies** — Python stdlib + git CLI (PyYAML used if present, minimal built-in parser otherwise)
2. **LLM-agnostic** — same scripts for Claude Code, Codex, Cursor, console, or manual use
3. **Detector never modifies; remediator modifies only the guarded auto-sync class**
4. **Identifying names (repo, workspace, client) never on audio/banner surfaces** — counts and pointers only
5. **Mutation is event-driven; only reads may poll**
6. **Fail closed, never force** — empty guard config disables; divergence/hook-failures stop and alert
7. **Composable** — exit codes, JSON output, shared state files

## Changelog

- **2.0.0 (2026-07-08):** three-layer redesign. Generic-only audio/banner (confidentiality rule), `~/.synthesis/quiet-audio` mute flag, report files + history, remediation hints, new `checkpoint_sync.py` (event-driven auto-commit/push: runtime remote guard, quiescence, shared throttle, ff-only push, distinct author, stale-lock detection), synthesis-console integration contract, scheduled-mutation explicitly disallowed. Origin: 2026-07-08 design review (lesson: alert-channel confidentiality + event-driven checkpoints).
- **1.1.0:** detector + count-only audio alerts.
