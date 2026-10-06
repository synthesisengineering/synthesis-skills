# Day-Start Checklist

Read at day-start. Execute in this order (each step depends on the one before it).
`<rituals>` is this skill's folder; `<W>` is the workspace name (the folder under
`~/workspaces/`). **Distributed mode:** each worker runs its workspace's steps and files its
artifact; the desk runs Steps 1 and 6 to 8 and folds worker artifacts per
[ritual-worker-contract.md](ritual-worker-contract.md).

Contents: 1 Temporal, state and health verification · 2 Context optimization · 3 Sync (3a
source code, 3b channels, 3c meeting transcripts, 3d inbox hygiene) · 4 Catch-up read · 5 PR
review queue · 6 Day plan · 7 Morning messages · 8 Record the day-start.

## 1. Temporal, State and Health Verification — RUN FIRST, every day

The LLM has no clock and its sense of "today" can drift across conversation gaps. Project-state cached in CONTEXT.md may be stale. Before any other day-start step, anchor today's date and verified project state from external sources.

- [ ] Run `date "+%Y-%m-%d %H:%M:%S %Z (%A)"` and record the output. This is today's authoritative date. If your in-context impression of the date differed, that is drift — treat other in-context impressions of time, intervals, and "last session" as also potentially drifted.
- [ ] **Board read.** `synthesis who` lists live sessions, their projects and claims; `synthesis inbox` shows and marks this session's unread messages. If other sessions are live, run the ritual in [Concurrent-Seats mode](mid-day-and-modes.md#concurrent-seats-mode-ritual). Claim only the files this ritual will write: `synthesis claim <today's plan> <CONTEXT.md> <session log> --goal "day-start"`.
- [ ] For each active project in the workspace's `index.yaml`, read its latest dated session entries and compare the recorded workday and outcomes with CONTEXT.md and index metadata. Inspect `git log -5 --pretty=format:"%h %ai %ci %s" -- projects/<id>/` and Git status separately for publication and pending changes. A commit timestamp is not a verified session date.
- [ ] Report disagreements between session records with both evidence sources and reconcile them under an accepted claim. Do not overwrite a workday because a commit landed overnight, in another timezone or after a delay. If dated evidence is missing or unreadable, report session-date verification as unavailable; Git cannot supply the missing workday.
- [ ] Invoke the `synthesis-checkpoint` skill on any project whose cached state may be stale — it is the codified protocol for this verification.
- [ ] **Protection health:** run `synthesis doctor`. One line per check after a first line that says healthy or not with counts: the runtime, the hooks each harness actually registers (Claude Code, Codex, Muse), the send, deploy and commit guards, and installed-versus-source drift. **A protective control that nobody monitors is one that is quietly broken** — this check exists because a dependency failure once disabled scanning silently while commits kept passing. If the doctor reports a failure, surface it in the brief as urgent and fix it before any commit-bearing or correspondence work. The guards fail closed, so a broken send or commit guard blocks rather than waves calls through; a check that cannot run at all is the one to fix first.
- [ ] **Context-integrity check:** run `python3 <synthesis-context-lifecycle>/scripts/context_doctor.py --root <knowledge root>` (or `--project <path>` for one project; `--json` for machines). Exit 0 healthy, 1 defects found, 2 cannot tell. It audits the records that break a cold resumption: missing tiers, budget overruns, status disagreements between index and CONTEXT.md, stale `last_session` fields, open items past their review horizon. The durable record is what lets another agent or another machine pick the work up. Exit 2 means the doctor could not establish ground truth; treat that exactly like a failing guard. Defects are not urgent in the way a failing commit guard is, so surface the count in the brief and fix the active project's defects before working it.
- [ ] **Portfolio review:** run `python3 <rituals>/scripts/portfolio_review.py`. It names at most three projects that claim `active` but have not moved in over 30 days, and asks one question about each: close it, pause it, or pick it up today. Surface those three in the day plan as decisions. **This is the outflow the project index otherwise lacks** — projects enter it and never leave, so on the corpus that motivated this check 37 of 63 supposedly-live projects had gone quiet for over 90 days, one of them for 619, and nothing surfaced it. The context doctor already computes freshness but reports it among 200+ warnings, and a signal inside 200 warnings is not a signal. Three decisions a day clears a large backlog in a couple of weeks and never feels like a task. The check treats `active` as meaning *I intend to touch this within 30 days*; anything else is `paused`, which is honest and reverses with one word. It exits 0 always and can never be the reason a ritual fails.
- [ ] **Stale-claim review:** `synthesis who --all` also lists sessions quiet for over 8 hours, marked STALE. **A dead session's claim is worse than a stale project: it does not merely clutter, it denies work to every future claim that overlaps it**, which is exactly what happened when three abandoned rows blocked real work for up to ten days. Releasing a claim stays **your** decision — report each stale claim in the brief; a session that needs the area messages the holder (`synthesis msg <session> "<text>"`) and only then takes it over with `synthesis claim <paths> --take`. An agent that could clear another session's claim on a timer would turn the advisory lock into a suggestion.
- [ ] **Ritual state read:** the session-start context already carries one ritual line (last close, streak, workdays started and never closed, weekly review owed). For the full view run `python3 <rituals>/scripts/ritual_state.py query summary --workspace <W>`. Report **this workspace's** row plus any open workday in the plan's header or brief; visible skips are recoverable skips. **There is no mutable state file and no read-modify-write** — the predecessor kept one `last_day_end` slot written by every seat, and on 2026-09-02 one seat's close overwrote another's. A lock would not have saved it: with perfect serialization the second writer still replaces the single slot. The fault was schematic, so the shape was deleted rather than guarded.
- [ ] **Weekly-review-owed check:** `python3 <rituals>/scripts/ritual_state.py query weekly-review --workspace <W>` answers `owed: true` when the latest review predates the most recent Friday. If owed, run the review in [weekly-and-longer.md](weekly-and-longer.md) in THIS session (either ritual direction, any mode). Each seat owes its own review: the query answers for the named workspace only and refuses an unscoped call unless the log names exactly one workspace, because one seat's Friday review had been silencing every other seat's gate. If a `synthesis-catchup-ledger` sweep already ran on/after that Friday, record its date instead of re-scanning — the ledger supersedes the review for its window.
- [ ] **Desk only — the coverage line:** `python3 <rituals>/scripts/ritual_workers.py coverage` prints `coverage: <workspace> <run type> <finished> (<outcome>) · <workspace> pending · ...` for every registered workspace. It goes first in the brief.

This step is the L2 (skill-rule) anchor of the temporal and continuity discipline. Client lifecycle hooks are L1; global `AGENTS.md` rules are L3. See `synthesis-context-lifecycle` Session Start Protocol for the rationale.

## 2. Context Optimization

**Archive FIRST, delete second. Never remove content from CONTEXT.md until it exists in its destination (sessions/ or REFERENCE.md). Two-phase commit.**

- [ ] Check CONTEXT.md line count for each active project. If >120 lines, archive before starting work.
- [ ] Archive completed items and old session summaries to `sessions/YYYY-MM.md` FIRST. **Retain the verified workday of the archived session. Label today's recording time separately when archiving earlier work; do not substitute a commit date or infer a workday from conversation continuity.**
- [ ] Archive any newly-stable facts to REFERENCE.md FIRST.
- [ ] Verify archived content exists in destination files.
- [ ] Only then rewrite CONTEXT.md with archived content removed.
- [ ] Reconcile `last_session` with the latest recorded session. Work actually done today, including this archive/repair activity, can have a new entry dated from step 1; that entry does not redate the work it archives.

## 3. Sync

This step has four sub-steps. They run in order — source code first (so any draft can ground itself in current code), then channels (so the catch-up read uses today's messages), then transcripts of any auto-recorded meetings, then inbox hygiene.

### 3a. Source-Code Sync

Before drafting the daily plan, sync every source-code repo the current workspace declares for daily sync. This makes sure any code-grounded drafts (PR reviews, technical replies, status messages citing specific files or commits) reference current state, not yesterday's.

- [ ] Enumerate the repos to sync. Primary source: `<workspace>/.agents/repos.yaml` — **every repo with `ritual_sync: yes`, on every run** (skip the whole workspace only if its manifest says `status: dormant`). Fallback when no `repos.yaml` exists: the workspace's canonical `AGENTS.md` "Workspace Repos" table, every repo marked Yes. Either way the declared list is the complete decision — do NOT re-apply your own judgment about which repos seem "active" (v2.12.1). Context/ai-knowledge repos are marked No and are published by `synthesis handoff` at day-end.
- [ ] Run `python3 <rituals>/scripts/repo_state.py --workspace-root ~/workspaces/<W> --fetch --ff`. It runs `git fetch --all` in each declared repo (all configured remotes; the repo's own `git remote -v` is the source of truth for its remote layout) and fast-forwards each declared default branch that is strictly behind its upstream and whose working tree is clean — never a merge or rebase that could introduce silent conflicts. When other seats are live (see Concurrent-Seats mode), pass `--skip <name>` for every repo a live session's claim covers; a held branch that moved reports as a decision with the holder named, never auto-forwards under them.
- [ ] If any branch is **diverged** (local has commits the remote doesn't, AND remote has commits local doesn't), do NOT auto-resolve. Surface it in the day-plan briefing: "develop diverged in `<repo>` — N local commits vs M remote." Decide explicitly: rebase, merge, or leave it for the owner.
- [ ] If a default branch is **ahead** of remote only (local commits not pushed), surface that too — it's a "do I push?" decision, not an auto-action. A repo with uncommitted changes is listed file by file and never pulled over.
- [ ] Report the touched repos with their before/after commit SHAs in the daily plan (e.g., "develop: aaaaaaa → bbbbbbb, 11 commits, includes ticket-id-here"). This gives the user a glanceable view of what arrived overnight.
- [ ] Report every declared repo in exactly one state — never "not scanned", which once hid seven repos on branches with no upstream and 39 invisible commits for weeks. The script prints them: `CURRENT` (fetched and level), `BEHIND` (behind only: `--ff` was not passed, or the repo was skipped for a live claim), `DECISION` (diverged or local-ahead, surfaced above), `DIRTY` (uncommitted changes, listed), **`BLIND`** (reachable, but the checked-out branch has no upstream, or HEAD is detached — a defect, not a status: name the branch and offer the `switch`), `UNREACHABLE` (no clone, or fetch failed — environmental), `EXCLUDED` (`ritual_sync: no` or dormant). It closes with the denominator: "N of M current, B behind, D decisions, X dirty, B blind, U unreachable, E excluded." Exit 2 means a repo is BLIND or UNREACHABLE; exit 1 means a decision or dirty tree waits.
- [ ] Note any new branches that appeared on remotes (`git branch -r` shows them) — those may be feature branches worth knowing about even if not yet ready for review.

### 3b. Channel Sync (Slack + Google Chat + email + documents + local messages)

- [ ] **Open the run:** `python3 <rituals>/scripts/sync_watermark.py begin --workspace <W> --label day-start`. A watermark is the last moment actually WRITTEN, never the last attempted, and this run will prove its own coverage ([sync-watermarks.md](sync-watermarks.md)).
- [ ] Check for new PRs, CI results, overnight pushes (now that local repos are current).
- [ ] **Run `/synthesis-slack-sync`** — the `synthesis-slack-sync` skill handles the full Slack sync protocol: verify connector auth, read all channels, re-read all threads with replies, check DMs, save to local transcripts, and update the action plan. Every read's `oldest` comes from `sync_watermark.py window --workspace <W> --surface slack --target <resolved id>`, and every saved read is recorded with `sync_watermark.py advance --workspace <W> --surface slack --target <resolved id> --through <latest>`. Configuration is in `.agents/slack-sync.yaml` per project.
- [ ] **Google Chat sync** — if the workspace declares `.agents/gchat-sync.yaml`: enumerate spaces fresh via the Chat space-list call and save the call's text output to a file (never a hand-maintained ID list — per-meeting spaces churn daily), then run `python3 <rituals>/scripts/gchat_preflight.py --config .agents/gchat-sync.yaml --spaces <that file> --json --out <declared.json>`. It takes the config's explicit `targets` (space ids with labels — the auditable core, since the enumeration shows every DM as "Unnamed Space") plus the enumeration filtered client-side by the config's `scope` (the wrapper's type filter is not trusted), prints the resolved-target table with a census by type and a BOUND line whenever the enumeration was capped or short (the wrapper pages at 100 and exposes no cursor), and writes the declared set the watermark gate consumes. Read each target with `oldest` from `sync_watermark.py window --surface gchat --target <space id>`, windowed by `createTime`; treat a full page as possibly-truncated (narrow the window and re-read); keep the raw `users/<id>` on every line beside any resolved name; save to the workspace convention (e.g., `transcripts/gchat/gchat-YYYY-MM-DD.md`); record each saved read with `sync_watermark.py advance --surface gchat --target <space id> --through <latest>` — a surface-level advance is refused once targets exist. A bounded enumeration is partial coverage: defer the surface with the bound as the reason, never advance past it. Same confidentiality handling as Slack DMs. Skip silently when no config exists.
- [ ] **Email sync** — from the workspace's `.agents/mailboxes.yaml` ([mailbox manifest](mailbox-manifest.md)): run `python3 <rituals>/scripts/mailboxes.py --manifest .agents/mailboxes.yaml --workspace <W> plan` for the due accounts and sweep each one's inbound mail AND the user's own sent mail per its transport (sent items are correspondence records too — the user's outbound exec mail is often the day's most consequential artifact). Record each swept account with `sync_watermark.py advance --surface email --target <address> --through <latest>` and each skipped one with `sync_watermark.py defer --surface email --target <address> --reason "<why>"` (`unreachable: …` when the transport failed). Close with `mailboxes.py --manifest .agents/mailboxes.yaml --workspace <W> report`: every due account must read SWEPT, UNREACHABLE, or DEFERRED — a BLIND account fails the ritual until swept or deferred. Save to the workspace convention (e.g., `transcripts/email/YYYY-MM-DD-<slug>.md`).
- [ ] **Document-comment sync** — when the workspace has an established docs-sweep practice (`transcripts/docs/` or explicit config): Drive documents modified in the window, open comment threads where the newest reply is not the user's (ball in their court), and engagement on documents the user shared out.
- [ ] **Local messages** — when the workspace runs iMessage or WhatsApp triage, run it per `synthesis-local-messaging` (notes and pointers, never copies of the messages).
- [ ] **Name any surface not swept.** The declared surface set is the complete decision (v2.12.1 applied to channels); a sync that skips one must say so in its report rather than reporting as complete.
- [ ] **Watermark gate:** every read target's `oldest` came from `sync_watermark.py window`, and every saved read was recorded with `advance`, its `--through` the `latest=` epoch `window` printed for that read. A read made through the harness's own connectors advances like any other; no extra token or receipt is needed. Now run `python3 <rituals>/scripts/sync_watermark.py status --workspace <W> --surface <s> --since run` with **every declared surface passed explicitly** and the declared read targets via `--targets-from` (the file the preflight scripts wrote this run, never a stored copy) — the store only knows what has already been written, so a status that consults only the store walks straight past a declared surface never swept (the command refuses an empty surface set for exactly that reason). Non-zero exit names each surface or target this run did not re-read: read it now or defer it with an explicit reason before the ritual proceeds.
- [ ] Run any project-specific sync steps (see project supplement), and any steps the workspace instructions add.

### 3c. Meeting Transcripts

After any standup, planning session, or design review with auto-generated notes (e.g., Gemini in Google Meet):

**Automated path (preferred)** — if the project uses `synthesis-meeting-transcripts`:
- [ ] **Run `/synthesis-meeting-transcripts`** — the skill searches Gmail/Drive for today's Gemini-generated meeting notes doc, fetches both the summary and the full word-for-word transcript, and saves to the configured meeting transcript archive. Configuration is in `.agents/meeting-transcripts.yaml` per project. Works with hosted Gmail/Drive connectors or a self-hosted multi-account MCP. Record the saved window with `sync_watermark.py advance --surface meetings --through <latest>`; a meeting whose transcript could not be saved is a gap to name, never a quiet day.
- [ ] Read the saved transcript and extract action items, decisions, status changes.
- [ ] Update CONTEXT.md with any new information from the meeting.

**Manual path (fallback)** — if no Gmail/Drive tooling is available:
- [ ] Download transcript from `~/Downloads/`.
- [ ] **Verify transcript completeness.** Check that the file contains BOTH a summary/notes section AND a full conversation transcript (speaker-attributed dialogue with timestamps). Many AI note-takers (Gemini, Otter, Fireflies) produce a summary by default but may omit the raw transcript. **If the file contains only a summary without the full transcript log, warn the user immediately** — the raw transcript is the primary source; summaries are lossy and may misattribute or omit statements.
- [ ] Move to the configured workspace meetings directory with naming convention: `standup-YYYY-MM-DD.md` or `meeting-TOPIC-YYYY-MM-DD.md`. The `{workspace}` value comes from the project's Slack sync config.
- [ ] Read transcript and extract action items, decisions, status changes.
- [ ] Update CONTEXT.md with any new information from the meeting.

### 3d. Inbox Hygiene (when `~/.synthesis/inbox-cleanup/scopes.yaml` exists)

Inbox cleanup is a chief-of-staff duty, and its reach follows the seat that invokes it (the inbox-cleanup skill's workspace-scope contract):

- [ ] Resolve scope: `resolve_scope.py --workspace <this workspace> --json`. A personal/all-scope seat sweeps every account; any other seat sweeps only its own workspace's accounts. **Exit 2 (unknown workspace, missing config) stops this step with the error surfaced — never improvise an account list.**
- [ ] Run the inbox-cleanup skill's sweep over exactly the resolved accounts, dry-run-first per that skill's workflow.
- [ ] Report per account against the resolved scope ("7 of 9 in scope, 7 swept"), naming any account skipped and why. Held items and new-sender questions go to the day plan's decisions region, not into silent limbo.

## 4. Catch-Up Read

**Cross-check before proposing action. An item that looks open in CONTEXT.md may already be resolved in Slack (or vice versa). The source of truth is the actual thread, not the action item list.**

- [ ] Review synced transcripts (`{workspace}/channels/`, `{workspace}/dms/`, `{workspace}/group-dms/` for today) and new messages for anything requiring action or awareness.
- [ ] For each potential action item: check the thread for replies, check CONTEXT.md for prior completion, check session logs. Only flag as open if ALL sources confirm it's unresolved.
- [ ] Note new action items, status changes on waiting items, and signals worth responding to.
- [ ] Remove or mark completed any CONTEXT.md items that Slack evidence shows are resolved.
- [ ] **Ownership vs visibility triage (v2.40.0).** Route every intake item by the [routing rules](ownership-routing.md) in order — manifest owner, deletion-unit test, movable-item seat — and stamp it `owner:`/`owner_rule:`. An item no rule claims becomes a CANDIDATE for the principal in this same turn: never double-recorded, never dropped.
- [ ] **Read every owned calendar for the look-ahead window,** each through its own account's connector (the account-routing guard picks the account). A window no calendar read covers is an unanswered question, not a free window. Report each collision with the movable side named, per the [routing rules](ownership-routing.md), and say which calendars were read, because "no conflicts" without that denominator is not a result.

## 5. PR Review Queue

- [ ] Check for PRs awaiting your review (lead integration review or peer review): `python3 <rituals>/scripts/pr_queue_scan.py --workspace <W>` lists, oldest first, review requests naming the principal, their own open PRs, and unreviewed PRs in the declared repos, and names every repo it could not read — an unscanned queue never reads as an empty one.
- [ ] Note age of oldest pending PR — anything >2 days old is a bottleneck.

## 6. Day Plan

- [ ] **Review yesterday's daily plan** (`daily-plans/YYYY-MM-DD.md`). Identify: uncompleted tasks to carry forward, draft messages that were never sent, items that are now stale due to overnight Slack activity, and "waiting on others" items that may have been resolved.
- [ ] **Cross-reference yesterday's plan with today's Slack sync.** A task marked incomplete yesterday may have been resolved overnight. A draft message from yesterday may no longer be accurate due to code changes, PR merges, or Slack replies. Do not blindly carry forward — verify each item is still valid and current.
- [ ] Create today's action plan in `daily-plans/YYYY-MM-DD.md` (shared infrastructure, not inside individual project directories or ~/Downloads). This creates a permanent archive. The structure and section vocabulary are in [plan-format.md](plan-format.md).
- [ ] The action plan should contain: tasks (prioritized with checkboxes), draft messages (with thread locators), things to know, waiting-on-others table, and everything else.
- [ ] **Apply decay tags:** any draft in the appreciation/kudos, acknowledgment, public-correction, or event-bound class gets a `**Decays:** YYYY-MM-DD (reason)` line at creation (kudos default: +2 workdays; event-bound: the event date). Keep the tag and stable `**Decay ID:**` when carrying an item, including on its due date; never reuse an ID for another obligation. Existing unkeyed items remain source-linked candidates without migration. See [deadline collection](decay-sweep.md).
- [ ] **No commitment without a date or a park (v2.14.0):** every new commitment line gets a do-by, a Decays tag, or an explicit `parked (reason)` marker before the plan is saved.
- [ ] **Seed `## 🌱 Lesson candidates` (v2.14.0)** — an empty H2 that any session appends one-liners to during the day; the day-end curates it (keep/drop).
- [ ] Update CONTEXT.md action items with new items from catch-up.
- [ ] Prioritize today's work: integration, reviews, communications, features, meetings.
- [ ] **Calendar Guardian — morning shield (v2.20.0).** Re-verify today against last night's review (invites land overnight): resolve new arrivals, then place/refresh holds over today's remaining open windows per the chief-of-staff skill's same-day shield — id-tracked, auto-expiring, releasable only from the holds ledger. Same-day requests route through triage (VIP tiers pass per config; everything else becomes a proposed later slot). Check prep exists for every meeting today; surface unanswered RSVPs and prep gaps as decisions. **Lead-time meetings (v2.26.0):** a flagged meeting today whose pack is missing or predates a reschedule is regenerated NOW from its declared sources — and the gap is named in the brief, because it means the owed day-end generation was missed.
- [ ] Update the action plan throughout the day as tasks complete or change — it is a living document, not a static morning capture.
- [ ] **Always include a clickable link to the action plan file** in your response when creating, updating, or referencing it. Use the absolute path in markdown link format: `[2026-03-23.md](/absolute/path/to/daily-plans/2026-03-23.md)`. Never use relative paths — they don't resolve in the IDE.

## 7. Morning Messages

- [ ] Post standup updates or morning status in relevant channels.
- [ ] Send motivational replies acknowledging overnight work (engineers who feel seen ship faster).
- [ ] Reply to any unanswered threads that need morning response.
- [ ] **Before drafting ANY reply for the user, re-read the actual Slack thread via MCP — not the local transcript.** The user may have already replied. Another team member may have resolved the question. Drafting from stale transcripts makes the user look absent-minded. Transcripts are caches for historical context; Slack is the source of truth for current thread state.
- [ ] **Ground ALL draft messages in actual systems — not just transcripts and meeting notes.** Before drafting ANY reply or message for the user, research the topic in primary sources first. This is not optional and applies to every draft, not just explicitly technical ones. See [draft-grounding.md](draft-grounding.md).
- [ ] When drafting messages for the user to send manually, ALWAYS include a thread locator: channel name, date/time of parent message, thread timestamp (TS), and the last unanswered reply with date/time and first ~10 words. The user needs this to find the thread instantly.
- [ ] Nothing sends without the principal's approval of the exact text: a send tool call is blocked until the principal types `approve <code>` for that message (see `synthesis approvals`).

## 8. Record the Day-Start

- [ ] `python3 <rituals>/scripts/ritual_state.py record --direction day-start --workspace <W> --date <today from step 1> --mode <mode> --session <this session's id> --pointer <today's plan>`. `--date` is the logical workday being opened, never inferred from the clock.
- [ ] Release the ritual's claims (`synthesis release`) or narrow them to what the day's work keeps. Nothing needs committing to switch harnesses on this Mac: the files on disk are the handoff. Day-end publishes.
