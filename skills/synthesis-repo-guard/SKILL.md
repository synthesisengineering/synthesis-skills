---
name: synthesis-repo-guard
description: "Workspace git-sync guard: detects unsynced repos, records session-attributed local handoff receipts, and batches private project-context commits for explicit remote handoff or day-end. Reports through confidentiality-safe channels."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.3.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Repo Guard

## The Problem

AI coding assistants and project-management tooling create and modify files continuously. A stopped task needs lightweight same-machine recovery immediately, while another computer needs a deliberate publication boundary. Treating both cases as an automatic commit creates noisy history and network latency; treating neither creates invisible local-only state. Tools that write files *outside* agent sessions (a project console writing status markers, manual edits) need the same attribution contract.

v1 of this skill detected stranded state and alerted with a count ("N repositories have unsynced changes"). Two failures emerged in practice:

1. **The alert was unactionable — and leaky if made actionable.** A count says nothing useful; speaking repo names would fix that, but repo/workspace names are often client names, and audio reaches whoever is nearby or on an unmuted call. Notification banners leak the same way during screen-shares.
2. **The alert fired on machine-fixable states.** Most unsynced state is exactly what automation should heal at the next sensible checkpoint. Alerting humans about machine-fixable problems trains them to ignore alerts.

## The Architecture — three layers

| Layer | Component | Job |
|-------|-----------|-----|
| Detector | `repo_sync_check.py` (scan) | Find dirty / ahead / behind / detached repos under a workspace root |
| Messenger | `repo_sync_check.py` (output) | Generic audio/banner ping + detailed report files + console tile data |
| Checkpointer | `checkpoint_sync.py` | Record local handoffs; batch exact context paths at explicit remote-sync events |

End state: same-computer client switching is filesystem-local and fast.
Cross-computer publication is batched and explicit. The synthesis-console shows
ambient status, and alerts remain rare and actionable.

## Confidentiality rule for alert surfaces (ABSOLUTE)

**Audio (`say`, alert sounds) and macOS notification banners never carry repo names, workspace names, or client names — only counts and a pointer ("details are in your synthesis console").** This holds at all times, not only while screen-sharing: presence detection is unreliable, and one leak outweighs the convenience. Identifying detail belongs exclusively in pull channels the user deliberately opens:

- `~/.synthesis/repo-guard/last-report.txt` / `last-report.json` / `history.jsonl` — written on every scan
- `~/.synthesis/repo-guard/checkpoint-state.json` — written on every checkpoint run
- the synthesis-console sync tile / page, which renders both

**Mute toggle:** all audible output (speech AND alert sounds) is suppressed while `~/.synthesis/quiet-audio` exists. synthesis-console exposes this as a header button; `touch`/`rm` the file works too. Muting loses nothing — reports and tile stay current.

## Detection vs. commit — scoping rules

`repo_sync_check.py` **detects and never modifies** — correct scope: every repo in the workspace.

There are two separate readiness transitions:

1. **Local handoff:** PostToolUse records structured edits by one client session; paired shell snapshots add net-new formatter, generator, and bulk-rewrite output without claiming unchanged pre-existing dirty paths. Stop writes an atomic receipt with branch, HEAD, file state, and content hashes. It performs no Git commit and no network call. If the client is interrupted before Stop, the pending manifest makes the work LOCAL_RECOVERABLE on the same filesystem.
2. **Remote handoff:** the flush-pending command batches only private project-context paths into exact-path commits. Source paths remain owned by their repository workflow and must already be clean and equal to their upstream before manifests retire.

## The checkpointer: local by default, remote by explicit event

`checkpoint_sync.py` runs at workflow events:

- **AI-tool Stop:** writes a local receipt when that client session has
  attributed repository changes. A Stop with no attributed repository changes
  is a cheap no-op because there is no new file state to preserve.
- **After a console cockpit write:** `--repo <written-file> --now` records
  a local producer manifest and receipt.
- **Day-end / mac-sync:** `--flush-pending` publishes exact private-context
  paths after the owning workflows publish any source paths.

**Deliberately not a launchd or cron job.** Wall-clock mutation can race
repositories across machines. Local receipts follow edit events; remote
mutation occurs only when the user invokes cross-machine sync or as part of
day-end. Read-only console polling remains safe.

### The auto-sync class + runtime guard

Config `~/.synthesis/checkpoint-sync.yaml` (copy `checkpoint-sync.example.yaml`) lists the class by explicit path and glob. Membership criteria: private knowledge/context repos (personal ai-knowledge repos, `*-<person>-private` workspace repos, daily plans). A configured checkout's isolated git worktrees inherit membership through their shared git-common-dir identity. Never source-code repos, never shared/public repos.

**The runtime remote guard is independent of config:** a repo is touched only if EVERY push remote starts with an allowed prefix (your private GitHub namespace). A glob that accidentally matches a repo with a client/org remote is excluded at run time, every time — config declares intent; the guard verifies reality. Empty `allowed_remote_prefixes` fails closed.

### Safety properties

- Stop never commits, pushes, fetches, stages, or changes branches.
- Shell attribution compares pre/post Git state and fails closed when its
  pre-tool snapshot is absent, unsafe, or belongs to another session.
- Remote publication orders exact-path context commit, fetch, then
  fast-forward push. Existing staged or dirty files outside the manifest
  remain untouched.
- Manifest writers, Stop receipts, remote flushes, and worktree retirement use
  one lifecycle lock. Retirement pins a freshly fetched remote-tracking
  commit, fsyncs a resumable intent before removal, invalidates old receipts,
  and completes idempotently after interruption. A missing path without this
  proof remains a fail-closed Stop error.
- A distinct commit author identifies batched remote-context commits.
- Divergence leaves the exact commit and manifest local and reports the
  block. Never rebase or force-push.
- Pre-commit hooks run normally. Never bypass them.
- Source paths and remotely publishable context paths are distinct fields
  in each client-session manifest.
- A first commit on a feature branch publishes that exact branch with an
  upstream.
- Active and stale Git index locks are reported and never deleted.
- A successful edit leaves a manifest even if Stop never runs. Remote
  publication retains manifests until source and context paths are verified
  upstream-current.

---

## Quick Start

```bash
# Scan ~/workspaces, write reports, print text summary
./repo_sync_check.py

# Machine-readable scan (console tile source)
./repo_sync_check.py --json --quiet

# Generic attention ping if dirty (mute-aware)
./repo_sync_check.py --speak --notify --dirty-only

# Preview pending remote publication
./checkpoint_sync.py --dry-run

# Record a same-machine Stop receipt
./checkpoint_sync.py --hook --quiet --notify

# Record a just-written producer file locally
./checkpoint_sync.py --repo ~/workspaces/example/daily-plans/today.md --now

# Publish pending project context after source repos are upstream-current
./checkpoint_sync.py --flush-pending

# Publish and retire one exact session without inspecting unrelated sessions
./checkpoint_sync.py --flush-session <session-id>
```

### Exit codes (both scripts)

| Code | repo_sync_check.py | checkpoint_sync.py |
|------|--------------------|--------------------|
| 0 | all clean & synced | requested readiness reached |
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

Turn-end remediation of the current session's attributed context paths plus
optional session-end verification:

```json
{
  "hooks": {
    "Stop": [
      { "hooks": [ { "type": "command",
        "command": "python3 <synthesis-repo-guard-root>/checkpoint_sync.py --hook --quiet --notify",
        "timeout": 120 } ] }
    ],
    "SessionEnd": [
      { "hooks": [ { "type": "command",
        "command": "python3 <synthesis-repo-guard-root>/repo_sync_check.py --dirty-only --speak --notify",
        "timeout": 60 } ] }
    ]
  }
}
```

### OpenAI Codex (`~/.codex/hooks.json`, with `features.hooks = true`)

```json
{ "hooks": { "Stop": [ { "hooks": [ { "type": "command",
  "command": "python3 <synthesis-repo-guard-root>/checkpoint_sync.py --hook --quiet --notify",
  "timeout": 120 } ] } ] } }
```

Each client session has its own hashed pending manifest under
`~/.synthesis/repo-guard/pending/`. Multiple agents can therefore coexist
without one hook committing, publishing, or overwriting another session's files.

### Cursor (`.cursor/settings.json`)

```json
{ "task.onEnd": "python3 /path/to/checkpoint_sync.py --hook --quiet --notify" }
```

### synthesis-console (command center)

- **Always-on sync tile:** polls `repo_sync_check.py --json --quiet` (read-only; lid-safe) and renders `checkpoint-state.json` outcomes.
- **Quiet-audio toggle button:** creates/removes `~/.synthesis/quiet-audio`.
- **"Sync now" button:** `checkpoint_sync.py --no-throttle`, an explicit remote-context handoff alias.
- **Producer receipts:** after writing a plan marker, the console records local state with `--repo <file> --now`.

### Scheduled execution — read-only only

If a tool supports no hooks at all, a scheduled **detector** run (`repo_sync_check.py --quiet`, reports only, no audio flags) is acceptable — it's read-only and interruption-safe. Do **not** schedule `checkpoint_sync.py`: mutation stays event-driven (see design rationale above). The console tile's polling normally makes scheduled detection unnecessary.

---

## Relationship to Other Skills

- **synthesis-mac-sync** — the full multi-machine sync operation (config files, credentials, all repos, with user approval). Repo-guard keeps same-machine work recoverable; mac-sync owns the explicit cross-machine publication transition.
- **synthesis-context-lifecycle / synthesis-daily-rituals** — those skills keep local project state current during work and publish it through remote handoff or day-end. `repo_sync_check.py` is the final day-end verification gate.

---

## Command Reference

```
repo_sync_check.py [--workspace W] [--max-depth N] [--quiet] [--json]
                   [--dirty-only] [--alert] [--speak] [--notify]
                   [--report-dir D] [--no-report]

checkpoint_sync.py [--config C] [--repo PATH] [--hook] [--now]
                   [--flush-pending | --flush-session SESSION_ID]
                   [--no-throttle] [--dry-run]
                   [--prepare-worktree-retirement PATH
                    --retirement-repository REPO --retirement-head SHA
                    --retirement-remote REMOTE --retirement-base REMOTE_REF]
                   [--complete-worktree-retirement INTENT]
                   [--reconcile-retired-worktree PATH
                    --retirement-repository REPO --retirement-head SHA
                    --retirement-remote REMOTE --retirement-base REMOTE_REF]
                   [--quiet] [--json]
                   [--speak] [--notify]
```

- `--speak/--notify/--alert` are generic + mute-aware on both scripts.
- `checkpoint_sync --repo` records one configured producer path locally; it does not commit or use the network.
- `--hook` consumes the calling session's JSON hook payload and never falls
  back to a workspace-wide mutation. `--flush-pending` is the explicit
  remote-context transition; `--no-throttle` is its console compatibility alias.
- `--flush-session` applies the same remote-readiness gates to one manifest
  selected by its exact session id. It does not read, validate, publish, or
  delete any other session manifest. Use it when unrelated pending work must
  remain recoverable while one fully published session transitions to
  `REMOTE_READY`.

---

## Design Principles

1. **Zero AI and zero external dependencies** — Python stdlib + git CLI (PyYAML used if present, minimal built-in parser otherwise)
2. **LLM-agnostic** — same scripts for Claude Code, Codex, Cursor, console, or manual use
3. **Detector never modifies; Stop is local-only; remote publication modifies only exact guarded context paths**
4. **Identifying names (repo, workspace, client) never on audio/banner surfaces** — counts and pointers only
5. **Remote mutation is explicit or day-end; only reads may poll**
6. **Fail closed, never force** — empty guard config disables; divergence/hook-failures stop and alert
7. **Composable** — exit codes, JSON output, shared state files

## Changelog

- **2.3.0 (2026-08-23):** adds a fail-closed exact-session remote handoff that
  retires one verified manifest without coupling it to unrelated pending
  sessions; preserves global flush behavior and fsyncs successful manifest
  retirement.
- **2.2.0 (2026-08-14):** makes retirement a lifecycle-locked, remote-pinned,
  fsynced, resumable transaction across manifests and receipts; resumes with
  the intent's exact content-addressed reconciler and compare-binds optional
  remote branch deletion to the verified head; keeps unexplained missing and
  unpublished paths fail-closed.
- **2.1.1 (2026-08-14):** clarifies that a clean no-edit task needs no empty receipt and that remote readiness compares complete branch heads rather than project-path history.
- **2.1.0 (2026-08-14):** separates local and remote readiness. Stop records atomic client-session receipts without Git or network mutation; interruption leaves a recoverable manifest; explicit remote handoff batches exact private-context paths only after source paths are upstream-current. Adds worktree identity, first-branch publication, generic commit messages, staged-index isolation, and integration fixtures.
- **2.0.0 (2026-07-08):** three-layer redesign. Generic-only audio/banner (confidentiality rule), `~/.synthesis/quiet-audio` mute flag, report files + history, remediation hints, new `checkpoint_sync.py` (event-driven auto-commit/push: runtime remote guard, quiescence, shared throttle, ff-only push, distinct author, stale-lock detection), synthesis-console integration contract, scheduled-mutation explicitly disallowed. Origin: 2026-07-08 design review (lesson: alert-channel confidentiality + event-driven checkpoints).
- **1.1.0:** detector + count-only audio alerts.
