# Preserved: the 2.45.1 SKILL.md, part 1 of 2 (verbatim)

The daily-rituals SKILL.md as it stood at 2.45.1, before the v5 rewrite: lines 18 to 206 of 500
(the introduction, configuration, script invocation, desk and workers, and the whole Day-Start
Checklist). It is kept word for word so nothing is lost (ruling D8). It is history, not
instructions: the commands in it (`synthesis exec-public`, the repo-guard manifests, the old
doctors) are gone. The rules that still hold live in the v5 files;
[coverage-map.md](coverage-map.md) says where each section went and why anything was retired.
Part 2 is [preserved-skill-v2-part2.md](preserved-skill-v2-part2.md).

Contents: Configuration · Script invocation · Distributed ritual execution · Day-Start Checklist
(1 Temporal & State Verification, 2 Context Optimization, 3 Sync with 3a to 3d, 4 Catch-Up Read,
5 PR Review Queue, 6 Day Plan, 7 Morning Messages).

---

# Daily Rituals — Global Checklists

Standard day-start and day-end rituals for synthesis engineering projects. These are the global (per-person) checklists. Each project may have a project-specific supplement that extends these with channel-specific sync, repo-specific checks, and stakeholder-specific communications.

Version history, the rationale behind each rule, and the incidents that produced them: [references/version-history.md](references/version-history.md). The distributed desk/worker contract: [references/ritual-worker-contract.md](references/ritual-worker-contract.md). Sync watermarks: [references/sync-watermarks.md](references/sync-watermarks.md). Daily plan format and vocabulary: [references/plan-format.md](references/plan-format.md). Draft grounding and formatting in full: [references/draft-grounding.md](references/draft-grounding.md). On a machine provisioned by the gated release, every `<…-root>` placeholder below resolves under `~/.synthesis/plugins/synthesis-skills/current/skills/`; never pin a versioned cache path — the Step 1 parity check fails when that pointer is missing or stale.

**Mandatory ritual evidence route:** Before recording a worker completion or beginning day-start, read [Ritual evidence](references/ritual-evidence.md). It specifies verified entrypoints, workspace artifact readiness, lesson-candidate custody, names-only credential-path coverage, and truthful refusal. The worker write is the completion; no historical artifact backfill.

Use the mandatory [mechanical owner map](references/mechanical-extraction.md) for transcript, channel, watermark, repository-state and grounding work; scripts do not replace interpretation or action authority.

Use [declared acquisition entries](references/acquisition-entry.md) for the supported meeting and Slack read adapters, account/source checks, raw custody, safe archives and evidence-bound watermark advancement. Connector reads count only through the declared connector-replay adapter; any other connector evidence remains UNKNOWN.
## Configuration

These values are user-specific. Update them for your environment.

| Setting | Value | Description |
|---------|-------|-------------|
| `daily_plans_path` | `daily-plans/` | Where daily action plans are saved (person-scoped, in the personal ai-knowledge repo) |
| `transcripts_path_in_private` | `transcripts/` | Relative subpath within each workspace-private repo. Workspace subdirs are NOT part of the path — they're implicit in the repo name (ADR-018) |
| `personal_repo` | `~/workspaces/<person>/ai-knowledge-<person>` | Absolute path to personal root. Daily plans, lessons, cross-workspace projects live here |
| `workspace_private_repo_pattern` | `~/workspaces/{workspace}/ai-knowledge-{workspace}-rajiv-private` | Path pattern for workspace-private repos (Type 3 content) |
| `index_yaml_path` | `projects/index.yaml` | Relative to personal_repo; project index file to update `last_session` |
| `lessons_path` | `lessons/` | Relative to personal_repo; where reusable lessons are stored (ADR-017) |
| `downloads_path` | `~/Downloads/` | Where meeting transcripts are initially downloaded |
| `alert_sound` | `/System/Library/Sounds/Glass.aiff` | macOS sound file for autonomous work alerts |
| `slack_auth_command` | tool-specific Slack auth flow | Command or UI flow to re-authenticate Slack for the current agent |

A project supplement (for example `daily-plans/daily-checklists.md`) lists the repos to sync, the channels and DMs with their ids, PR review targets, stakeholder communications, and any project-specific end-of-day steps; the global checklist invokes it at "Run any project-specific sync steps."

The [day-end installer](scripts/install_day_end.py) copies the launcher, nudge, its sibling [ritual-state query helper](scripts/ritual_state.py), and the query helper's owned runtime dependencies from the same release as executable files. Reinstallation refreshes that complete payload without changing the selected agent unless requested; the LaunchAgent retains its template schedule. The nudge queries ritual state without writing it and stays quiet when all expected workspaces have closed.

## Script invocation

Use `synthesis exec-public synthesis-daily-rituals/scripts/<name>.py` for the
five workflow helpers listed in [ritual evidence](references/ritual-evidence.md)
and for `ritual_state.py`. The installed owner verifies release, interpreter,
entrypoint and its owned dependencies. An unavailable or refused verified path
is a readiness failure; repair through the lifecycle owner, never direct Python.
Other scripts retain their specifically documented owners and are not implicitly
made callable through this entrypoint registry.

---

## Distributed ritual execution — desk and workers (v2.23.0)

Applies whenever a workers registry exists (default `~/.synthesis/ritual/workers.yaml`; absent registry = classic single-session ritual, no behavior change). Contract: [`references/ritual-worker-contract.md`](references/ritual-worker-contract.md).

- **The desk is the registry's `desk_seat`** — the ritual home. Only the desk produces the daily plan. One brief, one to-do list, one console; if a run produces more than one brief, the design has failed.
- **Each `active` worker executes its workspace's own checklist steps** (the syncs, the repo pass, the workspace-side triage below). **The default mode is an attended session rooted in that workspace**, run when the principal is working there, on that workspace's own schedule; a desk-dispatched subagent is the opt-in alternative for closing everything from one place. Either way the worker ends by writing the contract artifact to its registered `artifact_dir` — that write IS the worker's completion.
- **The principal is the dispatcher; the desk never triggers a worker.** No session can start work in another. The desk reports which workspaces are owed and the human opens the session that owes one. Attempts to dispatch by messaging sessions failed twice for the same structural reason — the target must already be open and attended — while the file-based path delivered both times. Contract: "The principal is the dispatcher."
- **Workspaces close on independent schedules.** Artifacts carry timestamps and `run_type` so the desk folds newest-per-workspace at any pass and refolds as later fragments land. Closing one workspace in the evening and another the next morning is normal operation.
- **The desk folds, never re-derives.** At every desk pass (day-start, mid-day, day-end) read the newest artifact per (workspace, run_type) for today, reconcile across workspaces — cross-workspace calendar and commitment conflicts are visible only here and are the desk's explicit responsibility, discharged through the overlap service (v2.40.0) — and produce the one brief.
- **The coverage line is mandatory and comes first** in every brief: each registered workspace as folded (run_type + finish time), **pending**, or **not scheduled** (`on-demand`/`dormant` per the registry). A registered-active workspace with no fresh artifact is reported *not covered* — never reconstructed from stale artifacts or desk guesswork.
- **Context isolation is the point.** The desk does not load a workspace's channels, repos, or transcripts inline; workers do not see each other or the combined picture. Reconciliation belongs to the desk alone (the parallel-dispatch rule from synthesis-project-management, applied to the day itself).
- **Storage separates; presentation converges (v2.24.0).** The plan the desk writes is a SHELL: person-scoped content plus pointers to each workspace's fragment (= its artifact). Workspace content is never copied into the person-side repository, so deleting a workspace's folders erases its data. Contract section: "Plan storage separation."

## Day-Start Checklist

Execute in this order (each step depends on the one before it). **Distributed mode:** each worker runs its workspace's steps and files its artifact; the desk runs Steps 1 and 8–10 and folds worker artifacts per the section above.

### 1. Temporal & State Verification — RUN FIRST, every day

The LLM has no clock and its sense of "today" can drift across conversation gaps. Project-state cached in CONTEXT.md may be stale. Before any other day-start step, anchor today's date and verified project state from external sources.

- [ ] Run `date "+%Y-%m-%d %H:%M:%S %Z (%A)"` and record the output. This is today's authoritative date. If your in-context impression of the date differed, that is drift — treat other in-context impressions of time, intervals, and "last session" as also potentially drifted.
- [ ] For each active project in the workspace's `index.yaml`, read its latest dated session entries and compare the recorded workday and outcomes with CONTEXT.md and index metadata. Inspect `git log -5 --pretty=format:"%h %ai %ci %s" -- projects/<id>/` and Git status separately for publication and pending changes. A commit timestamp is not a verified session date.
- [ ] Report disagreements between session records with both evidence sources and reconcile them under an accepted claim. Do not overwrite a workday because a commit landed overnight, in another timezone or after a delay. If dated evidence is missing or unreadable, report session-date verification as unavailable; Git cannot supply the missing workday.
- [ ] Invoke the `synthesis-checkpoint` skill on any project whose cached state may be stale — it is the codified protocol for this verification.
- [ ] **Protection-health check (v2.15.0):** run `python3 ~/.synthesis/git-hooks/_load_config.py --doctor`. It verifies the commit-boundary policy engine end to end: config parses, every pattern is valid for both `re` and `grep -E`, `core.hooksPath` is wired, the installed engine matches the skill source (drift detection), and the cwd repo's classification. **A protective control that nobody monitors is one that is quietly broken** — this check exists because a dependency failure once disabled scanning silently while commits kept passing. If the doctor reports UNHEALTHY, surface it in the brief as urgent and fix before any commit-bearing work. Read the severity the summary names: *blocking* problems refuse commits fail-closed until fixed; *advisory* conditions (drift, unwired hooksPath) mean the gate runs stale or not at all while commits proceed — fix those first, because an unhealthy engine is only "blocked, not unprotected" for the blocking kind.
- [ ] **Message-guard health check (v2.15.1):** run `python3 <synthesis-message-guard-root>/scripts/message_guard.py --doctor`. It checks static configuration and local controls: patterns parse, positive/negative scan controls pass, hook command markers and matchers cover the send/draft tool family, and the state directory is writable. This does not prove native invocation, semantic transport coverage, pending-message migration, or readback. Same rationale as the git-hooks check above: a protective control that nobody monitors is quietly broken. The guard fails closed, so UNHEALTHY means sends will be blocked, not unprotected — fix before any correspondence work.
- [ ] **Email capability and format monitoring:** when the message-guard email program is enrolled, have its configuration owner compare each selected client's fresh native tool catalog with its enrolled registry using `--capability-readiness`. Preserve and review added, removed or changed descriptors; no name-based automatic permission. For the email accounts/windows already selected by this ritual, collect raw sent/draft readbacks and run `--monitor-email` in bounded batches. Record complete pagination, supplied and unreadable message IDs, expected-message availability, and every violation in private evidence. A supplied empty batch is not a clean-mailbox result. This read-only monitoring adds no sends, corrections, subscriptions or scheduling; apply existing authorization before any response to a finding.
- [ ] **Context-integrity check (v2.16.0):** run `python3 <synthesis-context-lifecycle-root>/scripts/context_doctor.py --quiet --readiness local`. It audits every project in every configured source for the defects that break a cold resumption: missing tiers, budget overruns, an index.yaml status that disagrees with the project's own CONTEXT.md, `last_session` fields that disagree with dated session records, while surfacing uncommitted or unpushed context as local-only warnings. Same rationale as the two guards above, applied to the layer they all rest on — the durable record is what lets another agent or another machine pick the work up, and until today it was the only protective layer whose health nobody could check. Exit 2 means the doctor could not establish ground truth; treat that exactly like an UNHEALTHY guard. Defects are not urgent in the way an unhealthy commit gate is, so surface the count in the brief and fix the active project's defects before working it.
- [ ] **Dual-client parity check (v2.18.0):** run `python3 <synthesis-agent-conformance-root>/scripts/conformance.py parity` (from the SOURCE checkout, or pass `--source-root <synthesis-skills repo>`). Filesystem-only and fast: it verifies the two source manifests agree, both clients have the plugin installed, both clients carry the SAME newest version, and that version matches source main. This is the daily layer of the dual-runtime guarantee — CI enforces source parity and the release protocol documents the dual refresh, but only this check notices the day a release reaches one client and not the other. Any FAIL is a drift that gets fixed in this step (refresh the stale marketplace/plugin), not noted for later. A PENDING (v2.41.0) names a live seat mid-release: report it in the briefing and move on — never refresh a client under a live seat (see Concurrent-Seats Mode). Since v2.33.0 the same check verifies that the stable plugin path resolves to that installed version, so a missing or stale pointer is caught before any command runs from it.
- [ ] **Portfolio review (v2.27.0):** run `synthesis exec-public synthesis-daily-rituals/scripts/portfolio_review.py`. It names at most three projects that claim `active` but have not moved in over 30 days, and asks one question about each: close it, pause it, or pick it up today. Surface those three in the day plan as decisions. **This is the outflow the project index otherwise lacks** — projects enter it and never leave, so on the corpus that motivated this check 37 of 63 supposedly-live projects had gone quiet for over 90 days, one of them for 619, and nothing surfaced it. The context doctor already computes freshness but reports it among 200+ warnings, and a signal inside 200 warnings is not a signal. Three decisions a day clears a large backlog in a couple of weeks and never feels like a task. The check treats `active` as meaning *I intend to touch this within 30 days*; anything else is `paused`, which is honest and reverses with one word. It exits 0 always and can never be the reason a ritual fails.
- [ ] **Coordination archive:** run `python3 <synthesis-project-management-root>/scripts/coordination.py archive --json`. This moves only released rows older than 30 days and old messages whose exact sender and recipient are both archived. Active/recent/unknown rows, broadcasts, and ambiguous messages remain. A leased board publishes removal and reachable monthly archive history in one CAS; local archives are verified mirrors. A failed archive remains a visible maintenance failure, never authorization to release a claim or erase evidence.
- [ ] **Orphan snapshot maintenance (opt-in):** run `python3 <synthesis-project-management-root>/scripts/prune_tool_snapshots.py` (add `--dry-run` to preview). It archives verified snapshot bytes before removing them from the hot directory; only a uniquely identified released native seat, no pending manifest, and a snapshot older than one day qualify. Unknown, active, recent, malformed or redirected evidence remains. A missing snapshots directory reports zeros, not an error. Treat refusal as a maintenance finding, never permission to erase retained work.
- [ ] **Coordination-claim review (v2.27.0):** run `python3 <synthesis-project-management-root>/scripts/coordination.py stale`. It names active claims whose heartbeat has gone quiet, with physical evidence for each — a claimed worktree that no longer exists is close to proof the session is gone, while elapsed time alone is not. **A dead session's `active` row is worse than a stale project: it does not merely clutter, it denies work to every future claim that overlaps it**, which is exactly what happened when three abandoned rows blocked real work for up to ten days. Releasing a claim stays **your** decision — the surface reports and prints the exact `release --id` command, and never mutates the board. An agent that could clear another session's claim on a timer would turn the advisory lock into a suggestion. Exits 0 always.
- [ ] **Ritual state read (v2.28.0):** run `synthesis exec-public synthesis-daily-rituals/scripts/ritual_state.py query summary`. It derives per-workspace last-close, streak, and OPEN workdays (a day-start with no matching day-end) from an append-only log. Report **this workspace's** row plus any open workday in the plan's header or brief; visible skips are recoverable skips. **There is no mutable state file and no read-modify-write** — the predecessor kept one `last_day_end` slot written by every seat, and on 2026-09-02 one seat's close overwrote another's. A lock would not have saved it: with perfect serialization the second writer still replaces the single slot. The fault was schematic, so the shape was deleted rather than guarded.
- [ ] **Weekly-review-owed check (v2.14.0):** if today is on/after the most recent Friday AND `synthesis exec-public synthesis-daily-rituals/scripts/ritual_state.py query weekly-review --workspace <ws>` returns a date predating that Friday, or no date at all, the Weekly Loose-Ends Review is owed for THIS workspace — run the Day-End Step 10 scan in THIS session (either ritual direction, any mode) and record it with `record --direction weekly-review --workspace <ws> --date <today>`. Each seat owes its own review: since v2.37.0 the query answers for the named workspace only and refuses an unscoped call unless the log names exactly one workspace, because one seat's Friday review had been silencing every other seat's gate. If a `synthesis-catchup-ledger` sweep already ran on/after that Friday, record its date instead of re-scanning — the ledger supersedes the review for its window.

This step is the L2 (skill-rule) anchor of the temporal and continuity discipline. Client lifecycle hooks are L1; global `AGENTS.md` rules are L3. See `synthesis-context-lifecycle` Session Start Protocol for the rationale.

### 2. Context Optimization

**Archive FIRST, delete second. Never remove content from CONTEXT.md until it exists in its destination (sessions/ or REFERENCE.md). Two-phase commit.**

- [ ] Check CONTEXT.md line count for each active project. If >120 lines, archive before starting work.
- [ ] Archive completed items and old session summaries to `sessions/YYYY-MM.md` FIRST. **Retain the verified workday of the archived session. Label today's recording time separately when archiving earlier work; do not substitute a commit date or infer a workday from conversation continuity.**
- [ ] Archive any newly-stable facts to REFERENCE.md FIRST.
- [ ] Verify archived content exists in destination files.
- [ ] Only then rewrite CONTEXT.md with archived content removed.
- [ ] Reconcile `last_session` with the latest recorded session. Work actually done today, including this archive/repair activity, can have a new entry dated from step 1; that entry does not redate the work it archives.

### 3. Sync

This step has three sub-steps. They run in order — source code first (so any draft can ground itself in current code), then channels (so the catch-up read uses today's messages), then transcripts of any auto-recorded meetings.

#### 3a. Source-Code Sync

Before drafting the daily plan, sync every source-code repo the current workspace declares for daily sync. This makes sure any code-grounded drafts (PR reviews, technical replies, status messages citing specific files or commits) reference current state, not yesterday's.

- [ ] Enumerate the repos to sync. Primary source (v2.13.0): `<workspace>/.agents/repos.yaml` — **every repo with `ritual_sync: yes`, on every run** (skip the whole workspace only if its manifest says `status: dormant`). Fallback when no `repos.yaml` exists: the workspace's canonical `AGENTS.md` "Workspace Repos" table, every repo marked Yes. Either way the declared list is the complete decision — do NOT re-apply your own judgment about which repos seem "active" (v2.12.1). Context/ai-knowledge repos are marked No and are handled separately (checkpoint-sync / repo-guard).
- [ ] For each repo: `git fetch --all` to pull from all configured remotes, then fast-forward the default branches the team works on (typically `main` + `develop`; some teams also have `staging`, a long-running release branch, etc.). Use `git pull --ff-only` per branch — never a merge or rebase that could introduce silent conflicts. When other seats are live (see Concurrent-Seats Mode), fast-forward only branches no live seat holds; a held branch that moved reports as `decision` with the holder named, never auto-forwards under them.
- [ ] If any branch is **diverged** (local has commits the remote doesn't, AND remote has commits local doesn't), do NOT auto-resolve. Surface it in the day-plan briefing: "develop diverged in `<repo>` — N local commits vs M remote." Decide explicitly: rebase, merge, or leave it for the owner.
- [ ] If a default branch is **behind**, fast-forward it. If it's **ahead** of remote only (local commits not pushed), surface that too — it's a "do I push?" decision, not an auto-action.
- [ ] Report the touched repos with their before/after commit SHAs in the daily plan (e.g., "develop: aaaaaaa → bbbbbbb, 11 commits, includes ticket-id-here"). This gives the user a glanceable view of what arrived overnight.
- [ ] Report every declared repo in exactly one of four states — never "not scanned", which once hid seven repos on branches with no upstream and 39 invisible commits for weeks. `synced` (fetched, fast-forwarded, current); `decision` (diverged or local-ahead, surfaced above); **`BLIND`** (reachable, but the checked-out branch has no upstream — a defect, not a status: name the branch and offer the `switch`); `UNREACHABLE` (no clone, or fetch failed — environmental). Close with the denominator: "N of M repos current, D decisions, B blind, U unreachable."
- [ ] Note any new branches that appeared on remotes (`git branch -r` shows them) — those may be feature branches worth knowing about even if not yet ready for review.

The set of remotes for each repo comes from `git remote -v` inside that repo. The skill does NOT need a separate per-remote config — the repo itself is the source of truth for its own remote layout. When a workspace's primary remote changes (e.g., a migration from one Git host to another), the change happens in the local repo's `git remote -v`, and this step picks it up automatically.

#### 3b. Channel Sync (Slack + Google Chat + email + documents)

- [ ] Check for new PRs, CI results, overnight pushes (now that local repos are current).
- [ ] **Run `/synthesis-slack-sync`** — the `synthesis-slack-sync` skill handles the full Slack sync protocol: verify connector auth, read all channels, re-read all threads with replies, check DMs, save to local transcripts, and update the action plan. See that skill for the detailed protocol and the rationale behind each step. Configuration is in `.agents/slack-sync.yaml` per project, with `.claude/slack-sync.yaml` supported for existing projects.
- [ ] **Google Chat sync (v2.34.0)** — if the workspace declares `.agents/gchat-sync.yaml`: enumerate spaces fresh via the Chat space-list call and save the call's text output to a file (never a hand-maintained ID list — per-meeting spaces churn daily), then run `synthesis exec-public synthesis-daily-rituals/scripts/gchat_preflight.py --config .agents/gchat-sync.yaml --spaces <that file> --json --out <declared.json>`. It takes the config's explicit `targets` (space ids with labels — the auditable core, since the enumeration shows every DM as "Unnamed Space") plus the enumeration filtered client-side by the config's `scope` (the wrapper's type filter is not trusted), prints the resolved-target table with a census by type and a BOUND line whenever the enumeration was capped or short (the wrapper pages at 100 and exposes no cursor), and writes the declared set the watermark gate consumes. Read each target with `oldest` from `sync_watermark.py window --surface gchat --target <space id>`, windowed by `createTime`; treat a full page as possibly-truncated (narrow the window and re-read); keep the raw `users/<id>` on every line beside any resolved name; save to the workspace convention (e.g., `transcripts/gchat/gchat-YYYY-MM-DD.md`); record each saved read with `sync_watermark.py advance --surface gchat --target <space id> --through <latest>` — a surface-level advance is refused once targets exist. A bounded enumeration is partial coverage: defer the surface with the bound as the reason, never advance past it. Same confidentiality handling as Slack DMs. Skip silently when no config exists.
- [ ] **Email sync (v2.38.0)** — from the workspace's `.agents/mailboxes.yaml` ([mailbox manifest](references/mailbox-manifest.md)): run `mailboxes.py plan` for the due accounts and sweep each one's inbound mail AND the user's own sent mail per its transport (sent items are correspondence records too — the user's outbound exec mail is often the day's most consequential artifact). Record each swept account with `sync_watermark.py advance --surface email --target <address>` and each skipped one with `defer` and an explicit reason (`unreachable: …` when the transport failed). Close with `mailboxes.py report`: every due account must read SWEPT, UNREACHABLE, or DEFERRED — a BLIND account fails the ritual until swept or deferred. Save to the workspace convention (e.g., `transcripts/email/YYYY-MM-DD-<slug>.md`).
- [ ] **Document-comment sync (v2.19.0)** — when the workspace has an established docs-sweep practice (`transcripts/docs/` or explicit config): Drive documents modified in the window, open comment threads where the newest reply is not the user's (ball in their court), and engagement on documents the user shared out.
- [ ] **Name any surface not swept.** The declared surface set is the complete decision (v2.12.1 applied to channels); a sync that skips one must say so in its report rather than reporting as complete.
- [ ] **Watermark gate (v2.30.0):** a watermark is the last moment actually WRITTEN, never the last attempted, and the gate proves this run's coverage. The sweep opened with `synthesis exec-public synthesis-daily-rituals/scripts/sync_watermark.py begin --workspace <W> --label day-start`, every read target's `oldest` came from `sync_watermark.py window`, and every saved read was recorded with `sync_watermark.py advance` (per target for Slack and Chat), its `--through` the `latest=` epoch `window` printed for that read — the script accepts epoch seconds and Slack's fractional `ts` beside ISO-8601, `YYYY-MM-DD`, and `now`, and stores every form as ISO-8601 with an offset. Now run `synthesis exec-public synthesis-daily-rituals/scripts/sync_watermark.py status --workspace <W> --surface <s> --since run` with **every declared surface passed explicitly** and the declared read targets via `--targets-from` (the file `preflight.py --json --out` wrote this run, never a stored copy) — the store only knows what has already been written, so a status that consults only the store walks straight past a declared surface never swept (the command refuses an empty surface set for exactly that reason). Non-zero exit names each surface or target this run did not re-read: read it now or defer it with an explicit reason before the ritual proceeds.
- [ ] Run any project-specific sync steps (see project supplement).

#### 3c. Meeting Transcripts

- [ ] **Acquisition evidence:** read [references/acquisition-evidence.md](references/acquisition-evidence.md). At day-start probe every declared recorder account through its read-only identity adapter, then enumerate source documents for the exact window and compare provider/source IDs with saved archive headers. A healthy service is not sign-in. Meetings and Slack advances require `--acquisition-evidence`; missing/unreadable sources, incomplete pages, unexplained or explained-but-unclosed gaps, and missing in-window Slack controls leave watermarks unchanged. Gap decisions retain unknown coverage and remain in the ritual artifact.

After any standup, planning session, or design review with auto-generated notes (e.g., Gemini in Google Meet):

**Automated path (preferred)** — if the project uses `synthesis-meeting-transcripts`:
- [ ] **Run `/synthesis-meeting-transcripts`** — the skill searches Gmail/Drive for today's Gemini-generated meeting notes doc, fetches both the summary and the full word-for-word transcript, and saves to the configured meeting transcript archive. Configuration is in `.agents/meeting-transcripts.yaml` per project, with `.claude/meeting-transcripts.yaml` supported for existing projects. Works with hosted Gmail/Drive connectors or a self-hosted multi-account MCP.
- [ ] Read the saved transcript and extract action items, decisions, status changes.
- [ ] Update CONTEXT.md with any new information from the meeting.

**Manual path (fallback)** — if no Gmail/Drive tooling is available:
- [ ] Download transcript from `~/Downloads/`.
- [ ] **Verify transcript completeness.** Check that the file contains BOTH a summary/notes section AND a full conversation transcript (speaker-attributed dialogue with timestamps). Many AI note-takers (Gemini, Otter, Fireflies) produce a summary by default but may omit the raw transcript. **If the file contains only a summary without the full transcript log, warn the user immediately** — the raw transcript is the primary source; summaries are lossy and may misattribute or omit statements.
- [ ] Move to the configured workspace meetings directory with naming convention: `standup-YYYY-MM-DD.md` or `meeting-TOPIC-YYYY-MM-DD.md`. The `{workspace}` value comes from the project's Slack sync config.
- [ ] Read transcript and extract action items, decisions, status changes.
- [ ] Update CONTEXT.md with any new information from the meeting.

#### 3d. Inbox Hygiene (v2.21.0 — when `~/.synthesis/inbox-cleanup/scopes.yaml` exists)

Inbox cleanup is a chief-of-staff duty, and its reach follows the seat that invokes it (the inbox-cleanup skill's workspace-scope contract):

- [ ] Resolve scope: `resolve_scope.py --workspace <this workspace> --json`. A personal/all-scope seat sweeps every account; any other seat sweeps only its own workspace's accounts. **Exit 2 (unknown workspace, missing config) stops this step with the error surfaced — never improvise an account list.**
- [ ] Run the inbox-cleanup skill's sweep over exactly the resolved accounts, dry-run-first per that skill's workflow.
- [ ] Report per account against the resolved scope ("7 of 9 in scope, 7 swept"), naming any account skipped and why. Held items and new-sender questions go to the day plan's decisions region, not into silent limbo.

### 4. Catch-Up Read

**Cross-check before proposing action. An item that looks open in CONTEXT.md may already be resolved in Slack (or vice versa). The source of truth is the actual thread, not the action item list.**

- [ ] Review synced transcripts (`{workspace}/channels/`, `{workspace}/dms/`, `{workspace}/group-dms/` for today) and new messages for anything requiring action or awareness.
- [ ] For each potential action item: check the thread for replies, check CONTEXT.md for prior completion, check session logs. Only flag as open if ALL sources confirm it's unresolved.
- [ ] Note new action items, status changes on waiting items, and signals worth responding to.
- [ ] Remove or mark completed any CONTEXT.md items that Slack evidence shows are resolved.
- [ ] **Ownership vs visibility triage (v2.40.0).** Route every intake item by the [routing rules](references/ownership-routing.md) in order — manifest owner, deletion-unit test, movable-item seat — and stamp it `owner:`/`owner_rule:`. An item no rule claims becomes a CANDIDATE for the principal in this same turn: never double-recorded, never dropped.
- [ ] **Publish owned blocks; call the overlap service (v2.40.0).** Publish this seat's owned commitments to the shared time-block layer (real titles, hand-entered blocks for unreachable accounts), validate the layer, and run `overlap.py overlaps` for the look-ahead window. Report overlaps with the movable side named, and the layer's denominator — which seats published fresh, which are stale or missing — because "no overlaps" without it is not a result.

### 5. PR Review Queue

- [ ] Check for PRs awaiting your review (lead integration review or peer review).
- [ ] Note age of oldest pending PR — anything >2 days old is a bottleneck.

### 6. Day Plan

- [ ] **Review yesterday's daily plan** (`daily-plans/YYYY-MM-DD.md`). Identify: uncompleted tasks to carry forward, draft messages that were never sent, items that are now stale due to overnight Slack activity, and "waiting on others" items that may have been resolved.
- [ ] **Cross-reference yesterday's plan with today's Slack sync.** A task marked incomplete yesterday may have been resolved overnight. A draft message from yesterday may no longer be accurate due to code changes, PR merges, or Slack replies. Do not blindly carry forward — verify each item is still valid and current.
- [ ] Create today's action plan in `daily-plans/YYYY-MM-DD.md` (shared infrastructure, not inside individual project directories or ~/Downloads). This creates a permanent archive.
- [ ] The action plan should contain: tasks (prioritized with checkboxes), draft messages (with thread locators), things to know, waiting-on-others table, and everything else.
- [ ] **Apply decay tags:** any draft in the appreciation/kudos, acknowledgment, public-correction, or event-bound class gets a `**Decays:** YYYY-MM-DD (reason)` line at creation (kudos default: +2 workdays; event-bound: the event date). Keep the tag and stable `**Decay ID:**` when carrying an item, including on its due date; never reuse an ID for another obligation. Existing unkeyed items remain source-linked candidates without migration. See [deadline collection](references/decay-sweep.md).
- [ ] **No commitment without a date or a park (v2.14.0):** every new commitment line gets a do-by, a Decays tag, or an explicit `parked (reason)` marker before the plan is saved.
- [ ] **Seed `## 🌱 Lesson candidates` (v2.14.0)** — an empty H2 that any session appends one-liners to during the day; the day-end curates it (keep/drop).
- [ ] Update CONTEXT.md action items with new items from catch-up.
- [ ] Prioritize today's work: integration, reviews, communications, features, meetings.
- [ ] **Calendar Guardian — morning shield (v2.20.0).** Re-verify today against last night's review (invites land overnight): resolve new arrivals, then place/refresh holds over today's remaining open windows per the chief-of-staff skill's same-day shield — id-tracked, auto-expiring, releasable only from the holds ledger. Same-day requests route through triage (VIP tiers pass per config; everything else becomes a proposed later slot). Check prep exists for every meeting today; surface unanswered RSVPs and prep gaps as decisions. **Lead-time meetings (v2.26.0):** a flagged meeting today whose pack is missing or predates a reschedule is regenerated NOW from its declared sources — and the gap is named in the brief, because it means the owed day-end generation was missed.
- [ ] Update the action plan throughout the day as tasks complete or change — it is a living document, not a static morning capture.
- [ ] **Always include a clickable link to the action plan file** in your response when creating, updating, or referencing it. Use the absolute path in markdown link format: `[2026-03-23.md](/absolute/path/to/daily-plans/2026-03-23.md)`. Never use relative paths — they don't resolve in the IDE.

### 7. Morning Messages

- [ ] Post standup updates or morning status in relevant channels.
- [ ] Send motivational replies acknowledging overnight work (engineers who feel seen ship faster).
- [ ] Reply to any unanswered threads that need morning response.
- [ ] **Before drafting ANY reply for the user, re-read the actual Slack thread via MCP — not the local transcript.** The user may have already replied. Another team member may have resolved the question. Drafting from stale transcripts makes the user look absent-minded. Transcripts are caches for historical context; Slack is the source of truth for current thread state.
- [ ] **Ground ALL draft messages in actual systems — not just transcripts and meeting notes.** Before drafting ANY reply or message for the user, research the topic in primary sources first. This is not optional and applies to every draft, not just explicitly technical ones. See the draft rules below and [references/draft-grounding.md](references/draft-grounding.md).
- [ ] When drafting messages for the user to send manually, ALWAYS include a thread locator: channel name, date/time of parent message, thread timestamp (TS), and the last unanswered reply with date/time and first ~10 words. The user needs this to find the thread instantly.

---
