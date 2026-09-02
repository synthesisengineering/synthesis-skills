---
name: synthesis-daily-rituals
description: "Day-start and day-end checklists for synthesis engineering projects. Execute dependency-ordered rituals for context optimization, channel sync across Slack, Google Chat, email, meeting transcripts, and document comments, catch-up reads, PR reviews, day planning, and communications. Use when asked about: daily ritual, morning routine, day start, day end, daily checklist, morning checklist, end of day checklist, daily workflow."
license: "Apache-2.0"
depends_on:
  - synthesis-context-lifecycle
  - synthesis-project-management
  - synthesis-slack-sync
  - synthesis-repo-guard
  - synthesis-checkpoint
metadata:
  author: "Rajiv Pant"
  version: "2.34.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Daily Rituals — Global Checklists

Standard day-start and day-end rituals for synthesis engineering projects. These are the global (per-person) checklists. Each project may have a project-specific supplement that extends these with channel-specific sync, repo-specific checks, and stakeholder-specific communications.

Version history, the rationale behind each rule, and the incidents that produced them: [references/version-history.md](references/version-history.md). The distributed desk/worker contract: [references/ritual-worker-contract.md](references/ritual-worker-contract.md). Sync watermarks: [references/sync-watermarks.md](references/sync-watermarks.md). Daily plan format and vocabulary: [references/plan-format.md](references/plan-format.md). Draft grounding and formatting in full: [references/draft-grounding.md](references/draft-grounding.md). On a machine provisioned by the gated release, every `<…-root>` placeholder below resolves under `~/.synthesis/plugins/synthesis-skills/current/skills/`; never pin a versioned cache path — the Step 1 parity check fails when that pointer is missing or stale.

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

---

## Distributed ritual execution — desk and workers (v2.23.0)

Applies whenever a workers registry exists (default `~/.synthesis/ritual/workers.yaml`; absent registry = classic single-session ritual, no behavior change). Contract: [`references/ritual-worker-contract.md`](references/ritual-worker-contract.md).

- **The desk is the registry's `desk_seat`** — the ritual home. Only the desk produces the daily plan. One brief, one to-do list, one console; if a run produces more than one brief, the design has failed.
- **Each `active` worker executes its workspace's own checklist steps** (the syncs, the repo pass, the workspace-side triage below). **The default mode is an attended session rooted in that workspace**, run when the principal is working there, on that workspace's own schedule; a desk-dispatched subagent is the opt-in alternative for closing everything from one place. Either way the worker ends by writing the contract artifact to its registered `artifact_dir` — that write IS the worker's completion.
- **The principal is the dispatcher; the desk never triggers a worker.** No session can start work in another. The desk reports which workspaces are owed and the human opens the session that owes one. Attempts to dispatch by messaging sessions failed twice for the same structural reason — the target must already be open and attended — while the file-based path delivered both times. Contract: "The principal is the dispatcher."
- **Workspaces close on independent schedules.** Artifacts carry timestamps and `run_type` so the desk folds newest-per-workspace at any pass and refolds as later fragments land. Closing one workspace in the evening and another the next morning is normal operation.
- **The desk folds, never re-derives.** At every desk pass (day-start, mid-day, day-end) read the newest artifact per (workspace, run_type) for today, reconcile across workspaces — cross-workspace calendar and commitment conflicts are visible only here and are the desk's explicit responsibility — and produce the one brief.
- **The coverage line is mandatory and comes first** in every brief: each registered workspace as folded (run_type + finish time), **pending**, or **not scheduled** (`on-demand`/`dormant` per the registry). A registered-active workspace with no fresh artifact is reported *not covered* — never reconstructed from stale artifacts or desk guesswork.
- **Context isolation is the point.** The desk does not load a workspace's channels, repos, or transcripts inline; workers do not see each other or the combined picture. Reconciliation belongs to the desk alone (the parallel-dispatch rule from synthesis-project-management, applied to the day itself).
- **Storage separates; presentation converges (v2.24.0).** The plan the desk writes is a SHELL: person-scoped content plus pointers to each workspace's fragment (= its artifact). Workspace content is never copied into the person-side repository, so deleting a workspace's folders erases its data. Contract section: "Plan storage separation."

## Day-Start Checklist

Execute in this order (each step depends on the one before it). **Distributed mode:** each worker runs its workspace's steps and files its artifact; the desk runs Steps 1 and 8–10 and folds worker artifacts per the section above.

### 1. Temporal & State Verification — RUN FIRST, every day

The LLM has no clock and its sense of "today" can drift across conversation gaps. Project-state cached in CONTEXT.md may be stale. Before any other day-start step, anchor today's date and verified project state from external sources.

- [ ] Run `date "+%Y-%m-%d %H:%M:%S %Z (%A)"` and record the output. This is today's authoritative date. If your in-context impression of the date differed, that is drift — treat other in-context impressions of time, intervals, and "last session" as also potentially drifted.
- [ ] For each active project listed in the workspace's `index.yaml`, run `git log -5 --pretty=format:"%h %ai %s" -- projects/<id>/` and read the output. The most recent commit timestamp is the project's verified "last session." Trust this over any cached `last_session` field in CONTEXT.md or `index.yaml`.
- [ ] Cross-check each project's `index.yaml` `last_session` value against git log. If they disagree, the git log wins; update `index.yaml` before proceeding.
- [ ] Invoke the `synthesis-checkpoint` skill on any project whose cached state may be stale — it is the codified protocol for this verification.
- [ ] **Protection-health check (v2.15.0):** run `python3 ~/.synthesis/git-hooks/_load_config.py --doctor`. It verifies the commit-boundary policy engine end to end: config parses, every pattern is valid for both `re` and `grep -E`, `core.hooksPath` is wired, the installed engine matches the skill source (drift detection), and the cwd repo's classification. **A protective control that nobody monitors is one that is quietly broken** — this check exists because a dependency failure once disabled scanning silently while commits kept passing. If the doctor reports UNHEALTHY, surface it in the brief as urgent and fix before any commit-bearing work; the v2 engine fails closed, so an unhealthy engine means commits will be blocked, not unprotected.
- [ ] **Message-guard health check (v2.15.1):** run `python3 <synthesis-message-guard-root>/scripts/message_guard.py --doctor`. It verifies the pre-send correspondence gate end to end: patterns config parses, positive/negative scan controls pass, the PreToolUse wiring covers the send/draft tool family, and the state dir is writable. Same rationale as the git-hooks check above: a protective control that nobody monitors is quietly broken. The guard fails closed, so UNHEALTHY means sends will be blocked, not unprotected — fix before any correspondence work.
- [ ] **Context-integrity check (v2.16.0):** run `python3 <synthesis-context-lifecycle-root>/scripts/context_doctor.py --quiet --readiness local`. It audits every project in every configured source for the defects that break a cold resumption: missing tiers, budget overruns, an index.yaml status that disagrees with the project's own CONTEXT.md, `last_session` fields that git history contradicts, while surfacing uncommitted or unpushed context as local-only warnings. Same rationale as the two guards above, applied to the layer they all rest on — the durable record is what lets another agent or another machine pick the work up, and until today it was the only protective layer whose health nobody could check. Exit 2 means the doctor could not establish ground truth; treat that exactly like an UNHEALTHY guard. Defects are not urgent in the way an unhealthy commit gate is, so surface the count in the brief and fix the active project's defects before working it.
- [ ] **Dual-client parity check (v2.18.0):** run `python3 <synthesis-agent-conformance-root>/scripts/conformance.py parity` (from the SOURCE checkout, or pass `--source-root <synthesis-skills repo>`). Filesystem-only and fast: it verifies the two source manifests agree, both clients have the plugin installed, both clients carry the SAME newest version, and that version matches source main. This is the daily layer of the dual-runtime guarantee — CI enforces source parity and the release protocol documents the dual refresh, but only this check notices the day a release reaches one client and not the other. Any FAIL is a drift that gets fixed in this step (refresh the stale marketplace/plugin), not noted for later. Since v2.33.0 the same check verifies that the stable plugin path resolves to that installed version, so a missing or stale pointer is caught before any command runs from it.
- [ ] **Portfolio review (v2.27.0):** run `python3 <synthesis-daily-rituals-root>/scripts/portfolio_review.py`. It names at most three projects that claim `active` but have not moved in over 30 days, and asks one question about each: close it, pause it, or pick it up today. Surface those three in the day plan as decisions. **This is the outflow the project index otherwise lacks** — projects enter it and never leave, so on the corpus that motivated this check 37 of 63 supposedly-live projects had gone quiet for over 90 days, one of them for 619, and nothing surfaced it. The context doctor already computes freshness but reports it among 200+ warnings, and a signal inside 200 warnings is not a signal. Three decisions a day clears a large backlog in a couple of weeks and never feels like a task. The check treats `active` as meaning *I intend to touch this within 30 days*; anything else is `paused`, which is honest and reverses with one word. It exits 0 always and can never be the reason a ritual fails.
- [ ] **Coordination-claim review (v2.27.0):** run `python3 <synthesis-project-management-root>/scripts/coordination.py stale`. It names active claims whose heartbeat has gone quiet, with physical evidence for each — a claimed worktree that no longer exists is close to proof the session is gone, while elapsed time alone is not. **A dead session's `active` row is worse than a stale project: it does not merely clutter, it denies work to every future claim that overlaps it**, which is exactly what happened when three abandoned rows blocked real work for up to ten days. Releasing a claim stays **your** decision — the surface reports and prints the exact `release --id` command, and never mutates the board. An agent that could clear another session's claim on a timer would turn the advisory lock into a suggestion. Exits 0 always.
- [ ] **Ritual state read (v2.28.0):** run `python3 ~/.synthesis/rituals/ritual_state.py query summary`. It derives per-workspace last-close, streak, and OPEN workdays (a day-start with no matching day-end) from an append-only log. Report **this workspace's** row plus any open workday in the plan's header or brief; visible skips are recoverable skips. **There is no mutable state file and no read-modify-write** — the predecessor kept one `last_day_end` slot written by every seat, and on 2026-09-02 one seat's close overwrote another's. A lock would not have saved it: with perfect serialization the second writer still replaces the single slot. The fault was schematic, so the shape was deleted rather than guarded.
- [ ] **Weekly-review-owed check (v2.14.0):** if today is on/after the most recent Friday AND `query weekly-review` returns a date predating that Friday, the Weekly Loose-Ends Review is owed — run the Day-End Step 10 scan in THIS session (either ritual direction, any mode) and record it with `record --direction weekly-review`. If a `synthesis-catchup-ledger` sweep already ran on/after that Friday, record its date instead of re-scanning — the ledger supersedes the review for its window.

This step is the L2 (skill-rule) anchor of the temporal and continuity discipline. Client lifecycle hooks are L1; global `AGENTS.md` rules are L3. See `synthesis-context-lifecycle` Session Start Protocol for the rationale.

### 2. Context Optimization

**Archive FIRST, delete second. Never remove content from CONTEXT.md until it exists in its destination (sessions/ or REFERENCE.md). Two-phase commit.**

- [ ] Check CONTEXT.md line count for each active project. If >120 lines, archive before starting work.
- [ ] Archive completed items and old session summaries to `sessions/YYYY-MM.md` FIRST. **Use today's verified date (from step 1) when writing the entry header — do not infer from session continuity.**
- [ ] Archive any newly-stable facts to REFERENCE.md FIRST.
- [ ] Verify archived content exists in destination files.
- [ ] Only then rewrite CONTEXT.md with archived content removed.
- [ ] Update `last_session` date in `index.yaml` — use today's verified date.

### 3. Sync

This step has three sub-steps. They run in order — source code first (so any draft can ground itself in current code), then channels (so the catch-up read uses today's messages), then transcripts of any auto-recorded meetings.

#### 3a. Source-Code Sync

Before drafting the daily plan, sync every source-code repo the current workspace declares for daily sync. This makes sure any code-grounded drafts (PR reviews, technical replies, status messages citing specific files or commits) reference current state, not yesterday's.

- [ ] Enumerate the repos to sync. Primary source (v2.13.0): `<workspace>/.agents/repos.yaml` — **every repo with `ritual_sync: yes`, on every run** (skip the whole workspace only if its manifest says `status: dormant`). Fallback when no `repos.yaml` exists: the workspace's canonical `AGENTS.md` "Workspace Repos" table, every repo marked Yes. Either way the declared list is the complete decision — do NOT re-apply your own judgment about which repos seem "active" (v2.12.1). Context/ai-knowledge repos are marked No and are handled separately (checkpoint-sync / repo-guard).
- [ ] For each repo: `git fetch --all` to pull from all configured remotes, then fast-forward the default branches the team works on (typically `main` + `develop`; some teams also have `staging`, a long-running release branch, etc.). Use `git pull --ff-only` per branch — never a merge or rebase that could introduce silent conflicts.
- [ ] If any branch is **diverged** (local has commits the remote doesn't, AND remote has commits local doesn't), do NOT auto-resolve. Surface it in the day-plan briefing: "develop diverged in `<repo>` — N local commits vs M remote." Decide explicitly: rebase, merge, or leave it for the owner.
- [ ] If a default branch is **behind**, fast-forward it. If it's **ahead** of remote only (local commits not pushed), surface that too — it's a "do I push?" decision, not an auto-action.
- [ ] Report the touched repos with their before/after commit SHAs in the daily plan (e.g., "develop: aaaaaaa → bbbbbbb, 11 commits, includes ticket-id-here"). This gives the user a glanceable view of what arrived overnight.
- [ ] Note any new branches that appeared on remotes (`git branch -r` shows them) — those may be feature branches worth knowing about even if not yet ready for review.

The set of remotes for each repo comes from `git remote -v` inside that repo. The skill does NOT need a separate per-remote config — the repo itself is the source of truth for its own remote layout. When a workspace's primary remote changes (e.g., a migration from one Git host to another), the change happens in the local repo's `git remote -v`, and this step picks it up automatically.

#### 3b. Channel Sync (Slack + Google Chat + email + documents)

- [ ] Check for new PRs, CI results, overnight pushes (now that local repos are current).
- [ ] **Run `/synthesis-slack-sync`** — the `synthesis-slack-sync` skill handles the full Slack sync protocol: verify connector auth, read all channels, re-read all threads with replies, check DMs, save to local transcripts, and update the action plan. See that skill for the detailed protocol and the rationale behind each step. Configuration is in `.agents/slack-sync.yaml` per project, with `.claude/slack-sync.yaml` supported for existing projects.
- [ ] **Google Chat sync (v2.34.0)** — if the workspace declares `.agents/gchat-sync.yaml`: enumerate spaces fresh via the Chat space-list call and save the call's text output to a file (never a hand-maintained ID list — per-meeting spaces churn daily), then run `python3 <skill-root>/scripts/gchat_preflight.py --config .agents/gchat-sync.yaml --spaces <that file> --json --out <declared.json>`. It takes the config's explicit `targets` (space ids with labels — the auditable core, since the enumeration shows every DM as "Unnamed Space") plus the enumeration filtered client-side by the config's `scope` (the wrapper's type filter is not trusted), prints the resolved-target table with a census by type and a BOUND line whenever the enumeration was capped or short (the wrapper pages at 100 and exposes no cursor), and writes the declared set the watermark gate consumes. Read each target with `oldest` from `sync_watermark.py window --surface gchat --target <space id>`, windowed by `createTime`; treat a full page as possibly-truncated (narrow the window and re-read); keep the raw `users/<id>` on every line beside any resolved name; save to the workspace convention (e.g., `transcripts/gchat/gchat-YYYY-MM-DD.md`); record each saved read with `sync_watermark.py advance --surface gchat --target <space id> --through <latest>` — a surface-level advance is refused once targets exist. A bounded enumeration is partial coverage: defer the surface with the bound as the reason, never advance past it. Same confidentiality handling as Slack DMs. Skip silently when no config exists.
- [ ] **Email sync (v2.19.0)** — when the workspace routinely syncs email (established `transcripts/email/` practice or explicit config): sweep the window's inbound mail AND the user's own sent mail (sent items are correspondence records too — the user's outbound exec mail is often the day's most consequential artifact), using the workspace's designated email tooling and account. Save to the workspace convention (e.g., `transcripts/email/YYYY-MM-DD-<slug>.md`).
- [ ] **Document-comment sync (v2.19.0)** — when the workspace has an established docs-sweep practice (`transcripts/docs/` or explicit config): Drive documents modified in the window, open comment threads where the newest reply is not the user's (ball in their court), and engagement on documents the user shared out.
- [ ] **Name any surface not swept.** The declared surface set is the complete decision (v2.12.1 applied to channels); a sync that skips one must say so in its report rather than reporting as complete.
- [ ] **Watermark gate (v2.30.0):** a watermark is the last moment actually WRITTEN, never the last attempted, and the gate proves this run's coverage. The sweep opened with `python3 <skill-root>/scripts/sync_watermark.py begin --workspace <W> --label day-start`, every read target's `oldest` came from `sync_watermark.py window`, and every saved read was recorded with `sync_watermark.py advance` (per target for Slack and Chat). Now run `python3 <skill-root>/scripts/sync_watermark.py status --workspace <W> --surface <s> --since run` with **every declared surface passed explicitly** and the declared read targets via `--targets-from` (the file `preflight.py --json --out` wrote this run, never a stored copy) — the store only knows what has already been written, so a status that consults only the store walks straight past a declared surface never swept (the command refuses an empty surface set for exactly that reason). Non-zero exit names each surface or target this run did not re-read: read it now or defer it with an explicit reason before the ritual proceeds.
- [ ] Run any project-specific sync steps (see project supplement).

#### 3c. Meeting Transcripts

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

### 5. PR Review Queue

- [ ] Check for PRs awaiting your review (lead integration review or peer review).
- [ ] Note age of oldest pending PR — anything >2 days old is a bottleneck.

### 6. Day Plan

- [ ] **Review yesterday's daily plan** (`daily-plans/YYYY-MM-DD.md`). Identify: uncompleted tasks to carry forward, draft messages that were never sent, items that are now stale due to overnight Slack activity, and "waiting on others" items that may have been resolved.
- [ ] **Cross-reference yesterday's plan with today's Slack sync.** A task marked incomplete yesterday may have been resolved overnight. A draft message from yesterday may no longer be accurate due to code changes, PR merges, or Slack replies. Do not blindly carry forward — verify each item is still valid and current.
- [ ] Create today's action plan in `daily-plans/YYYY-MM-DD.md` (shared infrastructure, not inside individual project directories or ~/Downloads). This creates a permanent archive.
- [ ] The action plan should contain: tasks (prioritized with checkboxes), draft messages (with thread locators), things to know, waiting-on-others table, and everything else.
- [ ] **Apply decay tags (v2.14.0):** any draft in the appreciation/kudos, acknowledgment, public-correction, or event-bound class gets a `**Decays:** YYYY-MM-DD (reason)` line at creation (kudos default: +2 workdays; event-bound: the event date). Day-end's send-or-release pass keys off these lines.
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

## Draft Message Rules

Every draft is grounded, temporally correct, Slack-formatted, and numbered. The full protocol — research by question type, the investigate-first rule with its incident, the verification checklist, formatting examples, and appreciation quality — is in [references/draft-grounding.md](references/draft-grounding.md). The rules:

- **Ground every draft in primary sources before writing** — code, config, PRs, `git log`, deploy state, instruction files — never in transcripts or conversation memory alone; cite file paths, PR numbers, config values, or SHAs; flag any claim that cannot be verified instead of guessing. Applies to morning messages, mid-day replies, day-end communications, and ad-hoc requests alike.
- **Investigate first, ask questions later.** Before drafting a reply to a bug report or user issue, spend ten minutes in the code, config, and logs; if the fix fits in those minutes, ship it and lead the reply with the fix. Ask only for what you genuinely cannot obtain yourself.
- **Temporal integrity at send time, not write time.** Check whether the recipient already has the information, whether forward-looking statements still hold, whether a scheduled message uses the right tense, what happened since drafting, and whether the topic moved to another channel or medium — sweep every synced surface and email for the recipient and topic, re-pull full email threads before replying, and give drafts older than 24 hours full re-verification.
- **Verification checklist before finalizing:** every technical claim cites a source; every status claim is verified against the live system; every attribution is cross-checked (`gh pr view`, `git log`); no stale information — the target thread re-read via MCP AND the topic swept across other channels, DMs, and email; numbers come from tool output; temporal integrity passes.
- **Pre-send review gate:** every drafts section carries the verbatim reviewer notice before its first draft — drafts are research-backed starting points the human reads fully, edits into their own voice, and judges for the moment.
- **Slack formatting:** a blank line after every bullet (otherwise they collapse); Slack markdown (`*bold*`, `_italic_`, `>` quotes, backtick code); a thread locator on every reply draft (channel, human-readable parent time, author, first ~10 words; the TS as secondary reference); concise — over ~15 lines folds behind "Show more".
- **Draft numbering:** sequential integers (Draft 1, Draft 2, …), never letters or `K-2` sub-versions; before adding a draft, scan for the highest existing `Draft N` and use N+1; a retracted draft keeps its number with a `— retracted` marker and a pointer to the session log rather than renumbering.
- **Appreciation is specific:** name the work product, what made it good, and the observable impact; generic praise is weak and reads as automated.

---

## Daily Plan Structure

The daily plan is both a live dashboard and the day's record. **Preserve all information, reorganize for clarity:** never delete completed tasks, sent messages, timestamps, or decisions; consolidate freely so the file has ONE section per concern and reads cleanly top to bottom after every update — a full rewrite that preserves everything is maintenance, not data loss. The canonical structure, the H2 vocabulary the synthesis-console cockpit types (Decisions needed / Priority Tasks / Drafts — Ready to Send / Standup Highlights / Sent Messages / Waiting On Others / Open PR Queue / Sync state / Completed Today / Things to Know / Carried Items), the internal conventions the parser reads (decision options and `**Decided:**` markers, task done markers, draft `**Send to:**` and `**Sent:**` paragraphs, the 3-versus-4-backtick fence rule), and the file-revert protection protocol are in [references/plan-format.md](references/plan-format.md). Stay within that vocabulary; propose new section types as additions to the contract, never ad hoc. If a file revert is detected, re-read the entire file from disk, compare it with what you know was written, reconstruct anything missing from sync data and transcripts, and never silently accept the reverted file.

---

## Mid-Day Sync Protocol

The day-start checklist does a full sync. The user will ask for syncs repeatedly throughout the day ("sync from Slack", "what's new", "check channels"). **A sync request covers EVERY surface the workspace routinely syncs — not Slack alone, and not only chat surfaces (v2.19.0):**

1. **Slack** — always.
2. **Google Chat** — when `.agents/gchat-sync.yaml` exists; per target, from the declared set `gchat_preflight.py` writes this run (v2.34.0).
3. **Email** — when the workspace routinely syncs it (evidenced by an established `transcripts/email/` directory or an explicit config). Use the workspace's designated email tooling and account; sweep inbound AND the user's own sent mail for the window.
4. **Meeting transcripts** — when `.agents/meeting-transcripts.yaml` exists: any meeting that ended during the window gets its transcript fetched (or re-checked, for ones whose notes had not yet generated).
5. **Document comments** — when the workspace has an established docs-sweep practice (evidenced by `transcripts/docs/` or an explicit config): Drive documents modified in the window, and open comment threads addressed to the user.

**The complete-surface rule:** the surfaces a workspace syncs are a declared set, exactly like the repo list in the source-code sync (v2.12.1's no-agent-judgment rule applies here too). A sync that runs fewer surfaces than the workspace's declared/established set MUST name the omission explicitly in its report — "email and docs not swept this run" — never report as if the sync were complete. Origin incident (2026-08-09): a mid-day sync ran Slack and Chat only, while the day's most consequential correspondence — a CEO-facing email delivering two Google Docs — had happened entirely on the omitted surfaces; the gap was invisible because the sync reported quiet channels without naming what it had not checked.

**Run `/synthesis-slack-sync`.** The `synthesis-slack-sync` skill handles the Slack portion's complete protocol: read channels, re-read all threads with replies, check DMs, save to local transcripts, and update the action plan. See that skill for the detailed five-step protocol.

The key discipline encoded in that skill: **every sync must re-read ALL threads with replies from today**, not just fetch new channel-level messages. Thread replies don't appear as channel messages — skipping thread re-reads causes stale action plans and duplicate message sends.

**Every sync re-reads every declared target (v2.30.0).** A DM or channel read at day-start is not current at mid-day: "already read today" is a statement about the past, not about now, and a twelve-minute-old reply is the normal case for a DM. Open each sync with `python3 <skill-root>/scripts/sync_watermark.py begin --workspace <W> --label mid-day`, take each target's `oldest` from `sync_watermark.py window --target <resolved id>`, record each saved read with `sync_watermark.py advance --target <resolved id>`, and close with `sync_watermark.py status --workspace <W> --surface <s> --since run --targets-from <declared.json>` (the declared set written this run by the Slack skill's `preflight.py --json --out`, never a stored copy) — its BLOCKING list is exactly the set this sync skipped, and the sync is not complete while it is non-empty. The user's own outbound is first-class sweep state: list every owed item their messages discharged since the window opened, and never call anything "unanswered" or "unsent" on a read older than this run. Origin (2026-09-01): two mid-day syncs covered group DMs and channels only; a DM answered at 09:27 was reported unanswered at 17:51 on the strength of a 09:15 read.

**Record after every sync.** Any sync that creates or updates transcripts, daily plans, or context files must leave session-attributed local state. Day-start and mid-day sync do not push merely to make same-machine client switching work; day-end and explicit remote handoff publish the batch.

---

## Vacation / Observer Mode Ritual

Use this variant when the user signals they are not actively working ("I'm on vacation", "observer mode", "just keeping up", "don't want to send messages"). Common phrasings: "do the modified ritual", "do what you did the last few days", "stay in observer mode".

Observer mode is a specific sync and context pattern. Its changes become LOCAL_READY immediately and REMOTE_READY at day-end or explicit remote handoff.

### Steps

1. **Verify the date** — run `date` to confirm today and translate any day-of-week references correctly.
2. **Check Downloads** for standup transcripts, meeting notes, shared Google Docs, or forwarded emails. Move each to `~/workspaces/{workspace}/ai-knowledge-{workspace}-rajiv-private/transcripts/meetings/` with appropriate naming. Delete originals from Downloads.
3. **Full Slack sync** — run `/synthesis-slack-sync`. Read every channel, DM, group DM. Follow threads with replies. Save to transcripts.
4. **Create today's daily plan** in observer mode:
   - Header says "Mode: VACATION CATCH-UP (awareness only — team is operating independently)" or equivalent
   - NO draft messages to send
   - NO "things to do today" for the user
   - DO include: "Things to Know for Return" section with 5-10 items
   - DO include: any decisions, incidents, product signals, or concerns that would be hard to catch up on later
5. **Update CONTEXT.md** and session archive with the day's events. Follow the context lifecycle skill's archival protocol if needed.
6. **Record local handoff state** for files touched in this invocation. Publish them only in day-end or explicit remote-handoff mode.

### What Observer Mode Skips (Deliberately)

From the normal Day-Start:
- Step 6 "Morning Messages" — no messages posted on the user's behalf

From the normal Day-End:
- Step 3 "Communications" — no replies, no end-of-day status
- Step 5 "Career Amplification" — no thought leadership capture unless explicitly requested

### What Observer Mode Keeps (Non-Negotiable)

- Date verification
- Full Slack sync (no channels or DMs skipped, no threads skipped)
- Transcript capture
- Daily plan creation (in observer format)
- CONTEXT.md + session archive updates
- **Attributed local persistence** — observer mode records every changed file; its batch reaches the remote at day-end or explicit remote handoff.

---

## Day-End Checklist

**Distributed mode (v2.23.0):** each worker runs its workspace's close steps and files a `day-end` artifact; the desk folds artifacts, runs the guardian review and the publication boundary, and writes the one close-out with its coverage line.

### Day-End Modes (v2.14.0) — ask first, every time

Before Step 1, ask the user the one-letter mode question — **f** (full) / **q** (Quick Close) / **o** (observer) — every time, even when a mode seems obvious. If a launcher or opening prompt already named the mode, confirm it in one line instead of re-asking. Record the chosen mode in the state file (Step 7).

| Mode | Human moments | Steps run | Steps skipped |
|------|---------------|-----------|---------------|
| **Full** | as written | 1-11 | — |
| **Quick Close** (~10 min; the recommended default for ordinary evenings) | exactly three | 1, 4, 5, 7, 10 (only if owed), 11 | 2, 3, 6, 8, 9 |
| **Observer** | none | per the Vacation / Observer Mode section | comms + career steps |

**Quick Close's three human moments:** (1) the **send-or-release pass** over today's decay-tagged drafts (Step 4) — the step that protects overnight communication timing; (2) **keep/drop** on the day's `## 🌱 Lesson candidates` (Step 5); (3) the **closure read-back** — the agent ends with one on-screen paragraph: "Day closed. N sent, M released, lessons kept: X. Tomorrow opens with Y." Any audio accompanying it stays generic per the alert-confidentiality rules below. Everything else in Quick Close runs agentlessly around those three moments.

The Weekly Loose-Ends Review (Step 10) attaches to whichever ritual runs first on/after Friday, in any mode — a Friday Quick Close carries it. Every mode, observer included, writes the day-end state file in Step 7.

### 1. Transcript Sync

- [ ] **Run `/synthesis-slack-sync`** for final capture of the day. The `synthesis-slack-sync` skill ensures all channels, threads, and DMs are captured.
- [ ] **Google Chat final capture (v2.17.0)** — if the workspace declares `.agents/gchat-sync.yaml`, run the same Chat sweep as Day-Start Step 3b for the day's window (fresh space enumeration through `gchat_preflight.py`, per-target reads and advances, raw sender IDs preserved).
- [ ] **Email + document-comment final capture (v2.19.0)** — when the workspace syncs those surfaces (per Day-Start 3b's declared-set rule): the day's inbound and sent mail, meeting transcripts for any meeting that ended since the last sync, and document comments/engagement for the day's window. Name any surface not swept.
- [ ] **Watermark gate (v2.30.0):** the final capture opened with `sync_watermark.py begin --workspace <W> --label day-end` and recorded each saved read with `advance`; now run `python3 <skill-root>/scripts/sync_watermark.py status --workspace <W> --surface <s> --since run` with every declared surface and read target passed explicitly (same rule and same reason as Day-Start Step 3b's gate). The day does not close over a surface or target this run did not re-read: read it or defer it with a reason now.
- [ ] Update CONTEXT.md to mark any items resolved by day's conversations (so tomorrow's day-start does not re-propose them).

### 2. Source-Code Sync

End-of-day code sync ensures local main/develop reflects everything that landed during the day and that tomorrow's day-start begins from a clean, current state. Run the same source-code sync as Day-Start Step 3a — same workspace repo list, same fetch + fast-forward semantics, same surfacing of divergence.

- [ ] Read the pending repo-guard manifests first. For every recorded source path owned by this ritual session, run its required tests, inspect the staged index, commit only attributed paths, and push under the repository's branch, review, and deployment policy. Do not mutate another active claim. Any path that cannot be published keeps the affected project below `REMOTE_READY`.

- [ ] For every repo the workspace manifest marks for sync (`<workspace>/.agents/repos.yaml` `ritual_sync: yes`; fallback: the `AGENTS.md` table's Yes rows — the complete set, no activity judgment; v2.12.1/v2.13.0): `git fetch --all`, then `git pull --ff-only` on each long-running branch (typically `main` and `develop`).
- [ ] Surface any branches that are diverged or have local-only commits not yet pushed. These are decisions to make NOW, not at next day-start, so the agent can act on them while context is fresh.
- [ ] Note the day's net change per repo (e.g., "develop +11 commits, includes ticket-id-here"). This summary becomes part of the day-end log and feeds tomorrow's day-start briefing.

This step is intentionally not "merge ready PRs" — that's Integration Sweep below. This step is pure sync: pull latest state, surface divergence, do not modify history.

### 3. Integration Sweep

- [ ] Check PR queue — merge any ready PRs, push to staging.
- [ ] Close GitHub PRs with integration comments (if using adopt-and-adapt pattern).
- [ ] If a new version was deployed to staging or production, follow your team's release notification process. Best practice: list all PRs included, credit all contributors by name and PR number, post to both product and engineering channels.

### 4. Communications — the send-or-release pass (v2.14.0)

#### 4a. Calendar Guardian — tomorrow's review (v2.20.0)

Runs first inside Step 4, in **every mode including Quick Close** — the next-day review is the highest-value evening act the ritual performs, and it generates drafts the send-or-release pass below then handles. The review protocol itself lives in the chief-of-staff skill's **Calendar guardian** section; this step is its evening cadence.

- [ ] Review the **next working day** across every configured calendar — and on the last working day of the week, the **weekend too**. Run the full per-entry checklist (real? answered? prepared? outcome? shape? physically possible?) and the whole-day overcommitment check against config thresholds.
- [ ] **Place holds over tomorrow's remaining open windows** per the same-day shield: generically titled, busy, id-tracked in the holds ledger, auto-expiring. Release/move only holds the ledger says the agent created.
- [ ] Conflicts and overcommitment produce **named candidates to move with drafted reschedule notes** — into the plan's drafts region, where this step's parent pass picks them up. A warning without candidates is not done.
- [ ] Anything only the principal can decide → one line each in the plan's decisions region. Tomorrow's calendar picture → the plan's calendar section.
- [ ] **Lead-time prep packs (v2.26.0):** when `.agents/meeting-preps.yaml` exists, generate or refresh the prep pack for every flagged meeting whose lead window includes tomorrow — built from the declared `sources` (prior transcript, mandate sources, project contexts), per the v2.26.0 rules and the `.agents/meeting-preps.yaml` schema in [references/version-history.md](references/version-history.md); the pack states its own basis (which declared sources were read, and the newest source's date). This runs in every mode including Quick Close, because it rides the tomorrow-review that already does.

- [ ] Collect today's decay-tagged drafts (every `**Decays:**` line in today's plan) plus unanswered threads from today.
- [ ] For each item, one of three outcomes — nothing decay-tagged carries silently past its date: **send now** (with the user's one-tap approval; nothing sends without them), **re-date** with a stated reason on the Decays line, or **release** (strike through with a one-line why).
- [ ] Post end-of-day status updates; send appreciation for the day's contributions (grounded per the appreciation rule in the Draft Message Rules above).
- [ ] In Quick Close this pass is human moment #1: it caps at the tagged set plus a one-line "anything else you want to send tonight?" check.

### 5. Lessons Learned

- [ ] **Curate the day's `## 🌱 Lesson candidates` (v2.14.0):** present the accumulated one-liners from today's plan; the user answers keep/drop per line. Keepers get promoted to `lessons/` or folded into the owning project's docs; drops get struck through in place. In Quick Close this is human moment #2.
- [ ] Document any additional reusable lessons in `lessons/` (patterns, mistakes, solutions that apply beyond this session).
- [ ] Update project REFERENCE.md with any new stable facts discovered today.

### 6. Career Amplification

- [ ] Review today's work for content opportunities: blog posts, articles, videos, talks.
- [ ] Note ideas in a running list (see thought-leadership writing skill for the full workflow when ready to write).
- [ ] Themes to watch for: novel patterns, hard-won solutions, process innovations, team dynamics insights, industry observations.

### 7. Context Capture

**Date discipline (matches Day-Start Step 1 and the global agent rules).** All session-log entries and CONTEXT.md updates written tonight MUST use today's verified date—not a date inferred from session continuity or memory. If the conversation has been running for multiple days, the agent's sense of "today" may be wrong by hours or days. Re-anchor before writing.

- [ ] Run `date "+%Y-%m-%d %H:%M:%S %Z (%A)"` once at the start of this step. Use the output as today's authoritative date for every file write that follows. (If `synthesis-checkpoint` is loaded, invoke it instead — it does this anchoring plus a git-log cross-check.)
- [ ] For each project worked on today: append a session-log entry to `sessions/YYYY-MM.md` with today's verified date in the header. Format the date as ISO `YYYY-MM-DD` (e.g., `## 2026-05-27 (Wed) — Day-end summary`).
- [ ] Update CONTEXT.md. Refresh the "Last session" field with today's verified date and update "Recent Sessions" with a one-line summary. **Every live entry in an open-items section carries its own age:** stamp it `(as of YYYY-MM-DD, review Nd)` when you write it, and re-stamp it only when you have actually re-checked it — a stamp advanced without a check is a false receipt, which is worse than an obviously old one. Entries that are genuinely done are closed out into `sessions/YYYY-MM.md` — write them there, verify they landed, then remove them from CONTEXT.md. `context_doctor.py` reports a stamped entry as `item-currency` once it passes its review horizon (14 days when `review Nd` is omitted); match the horizon to the item — owed work at the default, backlogs and wishlists at `(as of YYYY-MM-DD, review 180d)` — and park a settled decision under a decisions heading, since the section heading is what the checker reads as owed.

- [ ] Update MEMORY.md if current state info is stale (version numbers, environment status, team assignments).
- [ ] Update `last_session` date in `index.yaml` for each active project worked on today — use today's verified date.
- [ ] **Local context gate:** run context_doctor.py --project <active-project-path> --readiness local for every project worked today. Structural defects block; expected local-only Git state remains visible.
- [ ] **Record the ritual (v2.28.0):** `ritual_state.py record --direction day-end --workspace <ws> --date <logical workday> --mode --outcome [--count k=v] [--pointer <session log>]`. **`--date` is the workday being closed, never inferred from the clock** — closes are routinely written the next morning, and one person's workspace workdays open and close at different times. Records are structured data capped at 2048B so the append stays atomic under concurrent seats; the narrative belongs in the session log the `--pointer` names. Every mode records, observer included; day-start uses `--direction day-start`.

### 8. Skills Maintenance

- [ ] If any installed skill copies changed, check whether those edits need to be synced back to the source repo. Use `synthesis-skills-manager` or check `.source.json` provenance files.
- [ ] If skills were updated in source repos, verify they were installed to the Claude Code, Codex, and cross-agent locations that use them.

### 9. Machine Sync

- [ ] Run mac-sync (credentials, config, git remotes across machines).

### 10. Weekly Loose-Ends Review (owed weekly — v2.14.0)

**Owed-weekly gating (replaces the v2.8.0 Friday-only rule).** The review is owed once per week, anchored to Friday, and tracked in `~/.synthesis/day-end/state.json`. Read `last_weekly_review`: if it is on/after the most recent Friday, skip this step silently. If it predates the most recent Friday and today is on/after that Friday, run the scan below — in whichever ritual notices first (Day-Start Step 1 checks the same condition), in any day-end mode including Quick Close — then update `last_weekly_review`. A `synthesis-catchup-ledger` sweep on/after that Friday counts as the week's review (record its date); and if this scan finds 2+ consecutive missed rituals, suggest running that skill — it is the recovery tool for broken cadence. This decoupling exists because a Friday-evening-only review is disabled by exactly the skip it is meant to catch.

**Scope: past 14 calendar days.** Look back from today through 14 days ago. This captures the current week + the previous week — enough to surface items deferred across one weekend boundary, which is the typical failure mode.

**Sources to scan (read each one; do not infer):**

- [ ] **Calendar Guardian — week and month horizons (v2.20.0).** Part of the owed-weekly review, so a skipped Friday still gets caught by the same gating:
  - **Week ahead:** sweep all configured calendars for collisions, overcommitted days (config thresholds), unanswered RSVPs, and prep-less meetings — while there is still time to move things. Flag every lead-time meeting (`.agents/meeting-preps.yaml`) in the coming week so research that needs more than a day starts early (v2.26.0). Candidates-to-move come with drafted notes, same contract as the nightly review.
  - **Month ahead:** scan for anything needing lead time — travel, conferences, deadlines, visits. Any commitment that should start an absence-coordination notification clock (its `notify_on_commit` cohort, or a lead-time deadline inside the coming month) gets flagged NOW; this scan is what makes "people hear as soon as it is known" true in practice rather than in intention.
- [ ] `daily-plans/YYYY-MM-DD.md` for the past 14 calendar days. In each plan, look for:
  - Drafts (`### Draft N: ...`) without a following `**Sent:**` marker — these are unsent and the deadline already passed
  - Items under `## Priority Tasks → Do today — not negotiable` that lack a completion marker (✅ or "DONE" or strikethrough)
  - Existing `## Carryover open items` / `## Stale targets` sections — these are last week's loose ends that may or may not still be relevant
  - Anything under `## Decisions needed from Rajiv` that did not get a decision recorded
- [ ] Each active project's `CONTEXT.md` "Open Items" / "Decisions Needed" / "Open Questions" sections — flag items whose surrounding text has not changed in 14+ days
- [ ] Each active project's `## Waiting On Others` table — flag rows whose "Last asked" / "Asked at" timestamp is >7 days ago (one full work-week without a follow-up signals the ask got buried or forgotten)
- [ ] `sessions/YYYY-MM.md` for the current AND previous calendar month — scan for explicit personal commitments (Rajiv saying "I'll do X tomorrow" or "I'll send Y by EOD") and verify each has a matching completion record. Pattern-match on first-person future-tense verbs in Rajiv's own text, not in quoted teammate messages.

**Classify each surfaced item:**

- **STILL RELEVANT** → carry into Monday by appending to Friday's daily plan `## Carried Items` section in the canonical format the cockpit reads. Include: the item description, the original date it surfaced, the original source (which plan / which CONTEXT.md / which Slack thread). This is what Monday's day-start picks up.
- **OBSOLETE** → annotate IN PLACE on the original source file with a one-line reason (e.g., "obviated by Y on YYYY-MM-DD", "stakeholder OOO through Z", "decision moot post-X"). These items stop appearing in future weekly reviews because they're now marked. Do NOT delete — the annotation is the record that the item was triaged.
- **AMBIGUOUS** → surface to the user with a brief context block. They decide carry-forward vs close. Do not guess; for items that touch other people's commitments or strategic direction, the user must be the one to call it.

**Output requirements:**

- [ ] Add a `## Weekly Loose-Ends Review` section to today's (Friday's) daily plan. Structure: scan summary at top (count of items by classification + per-source breakdown), then the explicit STILL RELEVANT list (these are what Monday picks up), then OBSOLETE-with-reason list (audit trail), then AMBIGUOUS list (decision queue for the user).
- [ ] If items in STILL RELEVANT need to be tracked across the weekend, populate today's daily plan `## Carried Items` section. (Monday's plan, when created, will pull from there as part of normal day-start.)
- [ ] Annotate OBSOLETE items in their ORIGINAL source files (not in this review section) so they get marked once and stay marked.
- [ ] Leave every changed plan and annotation session-attributed; Step 11 publishes the final day-end batch.

**Failure mode to avoid:** writing a `## Weekly Loose-Ends Review` section header without actually scanning the sources. The value is in the scan. If sources have not been read in this invocation, do not write the section — note "Weekly Loose-Ends Review skipped — scan not performed this invocation" in the plan and surface the gap to the user.

### 11. Remote Readiness and Final Verification

**This step is mandatory and is the final mutating day-end step.**

- [ ] Re-read the lease-backed coordination board. Do not mutate paths held by another active session; report them as active local work rather than defects in this ritual.
- [ ] Publish every pending source path owned by this ritual under its repository policy. Inspect status and the staged index before each exact-path commit; run required tests and normal hooks.
- [ ] Run `checkpoint_sync.py --flush-pending`. Any retained relevant manifest blocks day-end remote readiness.
- [ ] For every project worked today, run `context_doctor.py --project <path> --readiness remote` and `conformance.py continuity --project <path> --readiness remote`. Require PASS.
- [ ] Run `repo_sync_check.py` across the full workspace. Every path owned by this ritual must be clean and upstream-current. Dirty state protected by another active coordination claim is reported and left untouched.
- [ ] Verify intended remote heads independently. Record `REMOTE_READY` in day-end state only when the project gates pass; otherwise record `blocked` with the local recovery state intact.

This gate distinguishes incomplete publication from legitimate parallel work. It never sweeps another session, discards local changes, bypasses hooks, or turns a local-only pass into a cross-machine claim.

---

## Ritual Persistence Protocol

Day-start, mid-day sync, and observer mode leave their writes session-attributed and locally recoverable. They do not commit or push merely to preserve same-machine continuity. Day-end and explicit remote-handoff mode publish the batch.

### Local mode

Track every file this invocation changes. Update project tiers before a natural pause and release or narrow coordination claims. PostToolUse manifests and Stop receipts provide automatic local continuity; an interrupted run remains recoverable from its manifest plus Git status and diff.

### Remote mode

Publish source paths first under each repository branch, review, test, and deployment policy. Then flush exact private-context paths through synthesis-repo-guard. Before each source commit, inspect the full staged index and include only attributed paths. Never use broad staging, never touch another active claim, and never bypass hooks.

Commit messages follow the global hygiene rule: generic in public and private repositories, with no sensitive names, titles, rationale, or prior values. Git history is not a session transcript.

Remote publication is complete only when remote-mode context doctor and continuity conformance pass, intended remote heads are verified, and no relevant pending manifest remains.

---

## Autonomous Work and Audio Alerts

When the user signals stepping away ("going to take a shower", "heading out", "don't wait on me", "continue without me"):

1. **Activate autonomous mode** — complete all planned work without prompting for confirmations.
2. **On completion of any significant task**, play the audio alert. **Alert-confidentiality rule (v2.14.0, matching the synthesis-repo-guard v2 alert model):** spoken text and notification banners carry ZERO identifying content — no client, repo, workspace, project, or person names. Others hear speakers on calls and see banners on screen-shares. Generic wording only, and honor the mute flag:
   ```bash
   [ -f ~/.synthesis/quiet-audio ] || { afplay /System/Library/Sounds/Glass.aiff && \
   afplay /System/Library/Sounds/Glass.aiff && \
   afplay /System/Library/Sounds/Glass.aiff && \
   say "The current task is complete. Details are on your screen."; }
   ```
   `~/.synthesis/quiet-audio` (console-managed) silences all audio; on-screen detail is unaffected.
3. **If a blocker requires input**, play the alert FIRST (same generic wording — never speak the blocker's subject), then display the question on screen.
4. **This is not limited to deployments** — any significant milestone (PR review posted, integration complete, deployment done, tests passing after a fix) should alert if the user is away, always with the generic wording.

**Prerequisite:** the current tool must be authorized to run the local alert commands (`afplay` and `say` on macOS). If not, warn at the start of autonomous mode.

