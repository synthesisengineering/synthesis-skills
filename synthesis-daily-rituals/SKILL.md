---
name: synthesis-daily-rituals
description: "Day-start and day-end checklists for synthesis engineering projects. Execute dependency-ordered rituals for context optimization, Slack sync, catch-up reads, PR reviews, day planning, and communications. Use when asked about: daily ritual, morning routine, day start, day end, daily checklist, morning checklist, end of day checklist, daily workflow."
license: "Apache-2.0"
depends_on:
  - synthesis-context-lifecycle
  - synthesis-project-management
  - synthesis-slack-sync
  - synthesis-repo-guard
  - synthesis-checkpoint
metadata:
  author: "Rajiv Pant"
  version: "2.14.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Daily Rituals — Global Checklists

Standard day-start and day-end rituals for synthesis engineering projects. These are the global (per-person) checklists. Each project may have a project-specific supplement that extends these with channel-specific sync, repo-specific checks, and stakeholder-specific communications.

## v2.14.0 — Day-End Closure: two-speed day-end, owed-weekly review, decay tags, day-end state

v2.14.0 (2026-07-08) redesigns the day-end around the observed failure mode: on busy or tired evenings the WHOLE ritual gets skipped, and three things decay invisibly — outbound-communication timing (appreciation and replies lose value overnight), lessons that were warm at 5 PM, and the user's own closure on the day. A four-week reconciliation (via `synthesis-catchup-ledger`) showed batch send-passes succeeding whenever a ritual ran, every decay clustering on the zero-ritual days, and the Friday-only Weekly Loose-Ends Review silently disabled for three straight weeks because it lived inside the ritual being skipped. The design principle: make the default evening close small enough to never skip, make starting it one word, make skipping it visible, and decouple the weekly safety net from the evening ritual entirely.

1. **Two-speed day-end, always ask.** The day-end gains a first-class **Quick Close** mode (~10 minutes, exactly three human moments) alongside full mode and observer mode. The session asks the one-letter mode question every time — no time-of-day silent defaults. Spec: "Day-End Modes" block at the top of the Day-End Checklist.
2. **Weekly Loose-Ends Review is owed weekly, not Friday-evening-bound.** The review runs at the FIRST ritual on or after Friday — day-start included, any day-end mode included — tracked via the state file. See the rewritten Step 10 gating.
3. **Decay tags.** Time-sensitive drafts carry a `**Decays:** YYYY-MM-DD (reason)` line from creation. Plan generation applies the tag automatically to the classes field evidence shows decay fastest: appreciation/kudos and acknowledgments, public corrections, and event-bound items. Day-End Step 4 becomes an explicit send-or-release pass over the tagged set — nothing decay-tagged carries silently past its date.
4. **No commitment line without a date or a park.** Every new commitment entering a daily plan gets a do-by, a Decays tag, or an explicit `parked (reason)` marker. Single-mention items that get none of the three are how commitments vanish without a trace.
5. **Lesson candidates accumulate during the day.** Daily plans gain a `## 🌱 Lesson candidates` H2. Any session — mid-day syncs, checkpoint moments, ad-hoc work — appends one-line candidates as insights occur. Day-end curates (keep/drop) instead of recalling from scratch; "warm" moves from 5 PM to the moment of insight.
6. **Day-end state file (producer).** Every ritual, both directions, every mode, writes `~/.synthesis/day-end/state.json` (atomic temp+rename) and appends one line to `~/.synthesis/day-end/history.jsonl`:

   ```json
   {
     "last_day_end":   { "date": "2026-07-08", "mode": "quick", "outcome": "clean", "sent": 3, "released": 1 },
     "last_day_start": { "date": "2026-07-08" },
     "last_weekly_review": "2026-07-03",
     "streak_day_end": 4
   }
   ```

   `streak_day_end` = consecutive workdays with a completed day-end, computed from history at write time. Consumers: the synthesis-console day-end chip, the nudge's suppression check, and the day-start brief line ("day-end: ran Mon ✓ quick · skipped Tue").
7. **Launcher + nudge ship in `scripts/`.** The ritual is an Agent Skill and always runs INSIDE an agentic coding session — nothing here changes that. `scripts/day-end` is a *launcher, not a runner*: it opens an agent session (Claude Code by default; `DAY_END_AGENT_CMD` overrides) with the ritual invocation as the first prompt, purely to remove cold-start friction at the end of the day. `scripts/day-end-nudge.sh` + `scripts/com.synthesis.day-end-nudge.plist` show one generic macOS banner at 16:55 on weekdays unless the state file says today's day-end already ran — notification only, never a mutation, generic fixed text (see the alert-confidentiality rule below). Install steps follow.
8. **Audio-alert section aligned with alert confidentiality.** Spoken alerts and banners carry zero identifying content and honor the `~/.synthesis/quiet-audio` mute flag — matching the synthesis-repo-guard v2 alert model. The old `say "[user], [task description] is complete"` pattern is retired: task descriptions can name clients, repos, or people, and speakers/screen-shares leak.

**Consumer coupling:** synthesis-console renders `state.json` (day-end chip) and `**Decays:**` lines (draft badges). Producer-grammar changes here require the console's `docs/cockpit-design.md` to change in the same wave — the document-as-contract rule.

### Installing the launcher and nudge (macOS)

```bash
# Launcher on PATH (point the symlink at any PATH dir you use)
ln -sf ~/.claude/skills/synthesis-daily-rituals/scripts/day-end ~/.local/bin/day-end

# Nudge LaunchAgent (16:55 weekdays, state-aware, notification-only)
cp ~/.claude/skills/synthesis-daily-rituals/scripts/com.synthesis.day-end-nudge.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.synthesis.day-end-nudge.plist
```

The plist resolves the nudge script through `$HOME/.claude/skills/.../scripts/` — the installed copy — so ordinary skill reinstalls keep it current without touching launchd. After changing the plist itself: `launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.synthesis.day-end-nudge.plist`, then re-`bootstrap`.

## v2.13.0 — Per-workspace `repos.yaml` is the machine-readable repo list

In v2.13.0 (2026-07-08), the source-code sync steps (Day-Start 3a, Day-End 2) enumerate from the workspace repo manifest when one exists: `<workspace>/.agents/repos.yaml` — a symlink into the workspace's private context repo, generated and maintained per synthesis-mac-sync v1.6.0 (which owns the file's schema and lifecycle). Sync every repo with `ritual_sync: yes`. A manifest with `status: dormant` means "skip this workspace's source-code sync entirely — and never delete anything" (retention rule). The workspace `CLAUDE.md` "Workspace Repos" table remains the human-readable view and the FALLBACK source when no `repos.yaml` exists. The v2.12.1 rule applies identically to both sources: the declared list is the complete decision — no agent activity-judgment.

## v2.12.1 — Source-code sync scope: the workspace table decides (no agent activity judgment)

In v2.12.1 (2026-07-08), the source-code sync steps (Day-Start 3a, Day-End 2) drop the "associated with active work" qualifier from v2.7.0. The workspace's `CLAUDE.md` "Workspace Repos" table is the COMPLETE decision about what to sync: every repo the table marks **Yes** gets synced on every ritual run, whether or not it feels active. The agent must not re-apply its own judgment about which repos are "active" — that judgment layer is exactly what let a collaborator repo drift unnoticed for ~6 weeks (its default branch still tracked a legacy remote after a Git-host migration, silently accumulating "unpushed" commits that the repo guard then flagged repeatedly). Wherever the "associated with active work" phrasing survives in older version notes below, this rule supersedes it. A workspace that wants a repo excluded marks it **No** in the table, with the reason.

## v2.12.0 — Cockpit Mode: meeting-prep packs (`meeting-preps/` + `## 📋 Prep packs`)

In v2.12.0, the Day-Start ritual gains an optional **meeting-prep step** (runs inside Step 6, after the calendar fetch): for each substantive meeting on today's calendar, write a one-pager prep pack to `<knowledge-root>/meeting-preps/YYYY-MM-DD-HHMM-slug.md` and index today's packs in the day plan under a `## 📋 Prep packs` H2 (one list line per pack, linking to the consumer's `/prep/<source>/<slug>` route or the file path).

**What a prep pack joins** (the chief-of-staff briefing-book function): the calendar event (when/who) × relevant transcripts (search by attendee across the workspace's transcripts) × hot items from project CONTEXTs that mention the attendee or the meeting's subject × open commitments in both directions (their waiting-on entries; your unsent drafts to them).

**File contract:**
- Filename `YYYY-MM-DD-HHMM-slug.md` (24h start time; slug identifies the meeting, e.g. `jessica-payne-1-1`). Packs sort chronologically; "today's packs" is a filename-prefix scan.
- H1 = meeting title. A `**When:**` line and a `**Who:**` line (comma-separated attendees) near the top.
- Body H2s are free-form; the recommended skeleton is `Context` / `Open commitments` / `Since last time` / `Suggested agenda`.
- Packs are ritual-generated and updated by mid-day sweeps when new signals land (a transcript posts, a commitment discharges). Never hand-maintained.

**Which meetings get packs:** 1:1s, externals, and any meeting with an attendee who appears in waiting-on tables or open drafts. Routine standups don't need packs unless something notable is queued.

## v2.11.0 — Cockpit Mode: `## 📅 Calendar` section (typed consumer support)

In v2.11.0, Cockpit Mode plans gain a canonical `## 📅 Calendar` H2 that the plan-generation step (Day-Start Step 6) writes from the user's calendar. This is the file-based bridge that lets consumers (synthesis-console v0.12+) render the day's events, bind Tier-C slots to windows, and visualize preemption — without the consumer needing calendar access of its own. The agent fetches events via the user's calendar tool (e.g. Apple Calendar MCP) at plan-generation time and refreshes the section during mid-day sweeps, so same-day meetings appear within one sweep cadence.

**Canonical item shape** (one list line per event):

```markdown
## 📅 Calendar

- 09:00–09:30 · Exec staff sync · Tony, Jane, Marcelo
- 11:30–12:00 · CSA standup · CSA team
- 15:00–15:30 · 1:1 · Jessica Payne
```

Rules: 24-hour `HH:MM–HH:MM` range first, then ` · `, then the event title, then optionally ` · ` and a comma-separated attendee list. En-dash or hyphen both parse. Lines that don't match still render as plain markdown (Postel's Law — nothing is dropped). All-day events use the title-only fallback form (no time range).

**Tier-C window binding:** each `## 🎯 Today` slot H3 SHOULD name its window in the heading (e.g. `### Deep 1 — board memo (window 09:30–11:00)`). Consumers match slot windows against calendar events; an overlapping event that is not the slot itself renders as a preemption flag on the slot. The plan-generation step keeps slot windows consistent with the `**Budget:**` line's windows.

## v2.10.0 — Cockpit Mode: Budget-Bound, Stakes-Routed Day Plans

In v2.10.0 (2026-06-12), the day plan gains an alternative canonical mode — **Cockpit Mode** — for users whose discretionary time is scarce and preemption-prone (heavy meeting load, frequent same-day scheduling). The classic mode (full prioritized task board) remains valid; Cockpit Mode is the recommended default when the user's open-item count persistently exceeds what their calendar can absorb. Design rationale and the originating six-week evidence base live with the user's working-system design doc; the durable protocol is here.

**The three rules of Cockpit Mode:**

1. **Budget before backlog.** The plan generation step reads the user's calendar FIRST, computes discretionary windows, and commits at most ~70% of them — the remainder is an explicit preemption buffer. The plan header states the arithmetic (`Budget: windows … = N min. Committed: M min (≤70%). Buffer: N−M min`). A plan that ignores the calendar is a wish list.

2. **Stakes-routed outbound (the tier matrix).** Every outbound communication is classified at creation:
   - **Tier A — agent sends, clearly agent-labeled** (per the user's bot-labeling rule): routing/triage pings, scheduling requests, receipt acknowledgments, info relays with citations, follow-up nudges on delegated items. Sent within the work block; every send logged to a `## On your behalf` section in the day plan (the TICKER). Tier A never expresses the user's opinions, makes commitments, or touches sensitive relationships. Requires the user's standing approval of the matrix before activation; until then, Tier A routes to Tier B.
   - **Tier B — one-tap queue:** drafts in the user's voice (kudos, substantive replies) and decisions-with-recommendation, presented in batches of ≤5 with APPROVE / EDIT / SKIP affordances answerable in one line. Two review windows per day.
   - **Tier C — user-original:** deep work and relationship-critical writing. **Maximum 3 per plan**, each assigned to a named calendar window.
   Ambiguity routes to Tier B, never to Tier A.

3. **Preemption is normal, not failure.** When a same-day meeting lands on a committed window, the lowest-priority Tier-C item drops to the queue automatically — no re-planning ceremony. Dropped and expired items are caught by the `synthesis-catchup-ledger` ratchet (see that skill); decay rules apply at plan-generation time (stale kudos auto-expire to a consolidated-send; DECAYING items carry do-by dates; event-bound items expire at their event).

**Plan format additions (cockpit-vocabulary compatible):** a `**Budget:**` line in the header; one `## ⚡ Decision needed` H2 when a decision is pending (max ONE per day where possible); `## 🎯 Today — N deep items` (the Tier-C slots); `## ☑️ One-tap batch` (Tier B, with a queued-overflow paragraph); `## On your behalf` (Tier A log); `## 📰 Brief` (readable in ≤90 seconds). Consumers (synthesis-console) treat `On your behalf` as a new lower-row collapsible until typed support ships.

**Relationship to rituals:** day-start still runs the full sync stack (Steps 1–5 unchanged) — Cockpit Mode changes only Step 6 (Day Plan) and Step 7 (Morning Messages: Tier A items send instead of queueing, once the matrix is approved). The user's ritual calendar blocks become review windows; briefs should be prepared BEFORE the block begins whenever the agent runs scheduled/continuous.

## v2.9.0 — Temporal & State Verification as Day-Start Step 1; new synthesis-checkpoint dependency

In v2.9.0 (2026-05-27), the Day-Start ritual gains a new Step 1 — "Temporal & State Verification" — that runs BEFORE all other day-start steps. It anchors today's date from `date`, runs `git log` per active project to verify "last session," and reconciles cached `last_session` fields against git timestamps. Triggered by the 2026-05-27 inbox-cleanup mis-dated-session-log incident; codified to prevent recurrence in any synthesis project.

Step renumbering across the day-start: NEW Step 1 = Temporal & State Verification. Old Step 1 (Context Optimization) → Step 2. Old Step 2 (Sync) → Step 3, with sub-steps 3a/3b/3c. Old Step 3 (Catch-Up Read) → Step 4. Old Step 4 (PR Review Queue) → Step 5. Old Step 5 (Day Plan) → Step 6. Old Step 6 (Morning Messages) → Step 7. The Day-End checklist is unchanged in numbering; Day-End Step 7 (Context Capture) gains explicit push-confirmation language matching the new discipline.

New dependency: `synthesis-checkpoint` — a lightweight skill that codifies the date-verification + state-verification protocol. The day-start ritual delegates to synthesis-checkpoint for the per-project verification work in Step 1.

The discipline this enforces (cross-tool, codified in CLAUDE.md item 13c–13e and the synthesis-context-temporal-continuity project): treat session-log entry dates, "N days ago" claims, and CONTEXT.md fields as caches subject to drift. Verify against `date` and `git log` before quoting them into any output.

## v2.8.0 — Weekly Loose-Ends Review on Fridays

In v2.8.0 (2026-05-22), the Day-End ritual gains a Friday-only "Weekly Loose-Ends Review" step that scans the prior two weeks of work for incomplete, missed, or forgotten items and consolidates the surviving ones into a carryover list for Monday's day-start.

**Rule:** on Fridays, before the Repo Guard final-verification step, scan the past 14 calendar days of daily plans + project context files + open commitment tables. For every surfaced item, classify it as STILL RELEVANT (carry into Monday), OBSOLETE (annotate-and-close in place), or AMBIGUOUS (surface to user). The output is a `## Weekly Loose-Ends Review` section in Friday's daily plan plus a populated `## Carried Items` section in Monday's plan.

**Why:** the workweek's cracks accumulate invisibly. A missed close-of-business ritual on Wednesday means Thursday's plan doesn't pick up Wednesday's open threads. By Friday, several items can be quietly stranded. Without an explicit weekly catch, the user's mental model of "what's open" drifts from reality — and the longer the drift, the harder the eventual reconciliation. Running this on Friday afternoon catches stale items WHILE context is still warm; Monday begins with a clean carryover instead of an archaeological dig.

**Why Friday and not Monday:** Monday is when the carryover gets ACTIONED. Friday is when the carryover gets ASSEMBLED. Assembling on Monday means starting the week with backwards-looking work; assembling on Friday means closing the week with a clean handoff to next week. The split also lets the user (or the agent) drop OBSOLETE items into context that's still fresh — Monday's view of "is this still relevant?" is fuzzier than Friday's.

**Where in the day-end checklist:** new Step 10, just before Repo Guard (which stays the terminal step). The skill detects day-of-week and skips silently on non-Fridays. See Day-End Checklist below.

**Idempotent re-runs:** if a Friday day-end ritual is missed and the agent runs the Weekly Loose-Ends Review on a later weekday (Saturday catch-up, Monday morning if Friday was skipped), it should still produce the same scan output — the scan is date-bounded, not weekday-bounded. The Friday-default is about WHEN it normally fires, not about whether the scan is meaningful on other days.

## v2.7.0 — Source-Code Sync as a First-Class Ritual Step

In v2.7.0 (2026-05-21), source-code synchronization becomes an explicit, first-class step in both the day-start and day-end rituals — running BEFORE the daily plan is drafted (so any drafts that need to be grounded in code can read current source) and BEFORE end-of-day verification (so tomorrow's day-start begins from a clean, current state).

**Rule:** for every source-code repo associated with active work in the current workspace, fetch from all configured remotes and fast-forward the default branches (typically `main` and `develop`, plus any other long-running branches the team uses) BEFORE drafting the daily plan and BEFORE the end-of-day repo-guard verification. The skill stays generic — the list of repos per workspace is declared in the workspace `CLAUDE.md` (or equivalent project context file), not hardcoded.

**Why:**

- **Drafts must be grounded in current code.** The grounding protocol (see below) requires draft messages to be grounded in primary sources before sending. If local source is days behind origin, a draft that cites a function or PR may be quoting a stale version. Pulling first means the grounding research uses the current code.
- **Avoid surprise conflicts at end-of-day.** Running fetch + fast-forward at day-end (just before the repo-guard verification) surfaces upstream divergence early — the user doesn't discover at 6 PM that develop moved fifty commits and a feature branch needs rebasing.
- **One step, not "I'll do it later."** Folding it into the ritual makes it deterministic. The earlier `git fetch --all` checkbox in v2.6.0 and prior was easy to skip and only fetched (no fast-forward) — v2.7.0 makes the step substantive and visible.

**What goes where:**

- This skill defines the GENERIC pattern (fetch from all push remotes, fast-forward default branches, surface diverged or behind-state, report which repos were touched).
- The WORKSPACE-SPECIFIC list of repos lives in the workspace's `CLAUDE.md` (e.g., `~/workspaces/<workspace>/CLAUDE.md`'s "Workspace Repos" table). Each repo's specific multi-remote configuration is implicit from `git remote -v` inside that repo.
- The PROJECT-SPECIFIC supplement may add per-project considerations (e.g., "after fetch, check whether feature/X is stale and needs rebase"). See "How to Create a Project Supplement" near the end of this file.

**Sequence within day-start:** Context Optimization (Step 1) → **Source-code sync (Step 2a — NEW)** → Slack sync (Step 2b — was Step 2) → Meeting transcripts (Step 2c — was Step 2b) → Catch-up read (Step 3) → PR review queue (Step 4) → Day plan (Step 5) → Morning messages (Step 6).

**Sequence within day-end (v2.8.0+):** Transcript sync (Step 1) → **Source-code sync (Step 2 — v2.7.0)** → Integration sweep (Step 3) → … → **Weekly Loose-Ends Review (Step 10 — v2.8.0, Fridays only)** → Repo guard final verification (Step 11 — was Step 10 in v2.7.0).

## v2.6.0 — Draft Numbering Convention (numbers, not letters)

In v2.6.0 (2026-04-29 very late evening), the convention for labeling drafts in a daily plan is fixed to **sequential integers** (Draft 1, Draft 2, Draft 3, …) rather than alphabet letters (Draft A, Draft B, …).

**Rule:** the first draft of the day is Draft 1. Each subsequent draft increments by 1. No letter labels. No K-2 / K-3 sub-versioning — if a single piece of work produces multiple draft messages (e.g., the same praise routed to two audience-specific channels), each one gets its own integer (Draft 11, Draft 12, Draft 13). The chronological count of drafts in the plan equals the highest integer in use, which makes it easy to answer "how many drafts today?" by reading a single label.

**Why:** numbers are easier to count at a glance, have no 26-item ceiling, and don't impose a mental "is K the 11th letter?" tax. The K-2 / K-3 sub-versioning that letter-labels invite is uglier than 11 / 12 / 13 and creates label-shape inconsistency in the file. Letter labels also make it harder to grep for "all drafts from #N onward" because alphabet ordering is lexicographic, not arithmetic.

**Retraction handling:** if a draft is retracted (caught fabrication, sent-then-deleted, etc.), reserve the number with a brief marker — e.g., `### Draft 8 — retracted` plus a one-line note pointing to the session log — rather than renumbering subsequent drafts. Renumbering after a retraction creates label-drift across the file and any cross-references in chat. The reserved number is the durable record that the slot existed.

**Cross-file consistency:** when renumbering a daily plan that's already been referenced from CONTEXT.md or session logs (those use the labels in effect at the time), update only the daily plan and add a brief note acknowledging the cross-reference gap. Historical narrative in session logs preserves the labels in use at the time — that's the right behavior, not a bug.

**Pre-draft check:** when adding a new draft to a daily plan, the first thing the agent does is scan the file for the highest existing `Draft N` integer and use N+1. No alphabet thinking.

## v2.5.0 — Draft Fence Convention (nested code blocks)

In v2.5.0 (2026-04-29), the canonical fence convention for draft message bodies is documented to handle the case where a draft contains its own triple-backtick code blocks (install commands, code samples, log excerpts).

**Rule:**

- **Default fence for a draft body is 3 backticks** (` ``` `). Use this when the message body contains no triple-backtick code blocks.
- **If the draft body contains ANY internal triple-backtick blocks**, the outer fence must be at least one backtick longer than the longest internal fence. In practice this means **4-backtick outer fence** (` ```` `) when the message contains 3-backtick blocks.

**Why:** CommonMark closes a fenced code block at the first fence of equal-or-greater length. A 3-backtick outer wrapper is closed by the first 3-backtick inner fence — splitting the draft into multiple disjoint blocks and breaking the synthesis-console renderer (which attaches its action bar to the first fenced block after `**Send to:**`). A 4-backtick outer wrapper survives 3-backtick inner blocks unchanged; the inner fences become literal content of the outer fence, which is exactly what we want for a draft body containing install snippets or code samples.

**Pasting into Slack:** when the user clicks Copy in synthesis-console, the action reads `.innerText` from the rendered `<pre>` block — outer fence delimiters are stripped, inner ` ``` ` markers are preserved as literal text. Slack then re-interprets the inner ` ``` ` as Slack code blocks. End-to-end behavior is correct.

**Cross-reference:**

- Consumer-side handling lives in synthesis-console `docs/cockpit-design.md` "Drafts" section (the consumer is being updated to handle multi-segment drafts robustly via `augmentDraftBlocks`, but the producer-side convention here is independently correct and should be applied regardless).
- Lesson backing this rule: `lessons/2026-04-29-document-as-contract-with-llm-producers.md`.

## v2.4.0 — Canonical Plan Format Contract

In v2.4.0 (2026-04-29), the daily plan file format became a versioned contract between this skill (the producer) and synthesis-console v0.8+ (the consumer that renders plans as a cockpit dashboard).

The contract is defined by the **canonical H2 vocabulary** below. The console's parser is tolerant of synonyms and emoji prefixes, but agentic skills (LLMs) must prefer the canonical names where possible because:

- Canonical names are unambiguously typed by the console (NEEDS YOU / TODAY / DRAFTS / lower-row collapsibles)
- Synonyms are accepted via substring + case-insensitive match, but each new variant adds parser maintenance burden
- Non-canonical names fall through to "other" and render as plain markdown — visible but not specially typed

When the LLM driving this skill decides to deviate from the template, it MUST stay within the recognized vocabulary table (next section). New section types should be proposed as additions to this contract, not invented ad-hoc.

The **producer-consumer contract** is documented in two places:
- This file's "Canonical Plan Format" section below (authoritative for skill writers).
- `synthesis-console/docs/cockpit-design.md` (authoritative for parser implementers).

These two files must stay in sync. When changing one, update the other in the same commit.

## v2.3.0 — Workspace-Rooted Paths

In v2.3.0 (2026-04-22), path configuration changed to reflect the ai-knowledge phase 2 architecture: transcripts live per-workspace in `ai-knowledge-<workspace>-<person>-private/transcripts/`; daily plans and lessons live person-scoped in `ai-knowledge-<person>/` at top-level (no `_` prefix). See synthesis-slack-sync v2.0.0 for the complementary configuration schema.

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

---

## Day-Start Checklist

Execute in this order (each step depends on the one before it).

### 1. Temporal & State Verification — RUN FIRST, every day

The LLM has no clock and its sense of "today" can drift across conversation gaps. Project-state cached in CONTEXT.md may be stale. Before any other day-start step, anchor today's date and verified project state from external sources.

- [ ] Run `date "+%Y-%m-%d %H:%M:%S %Z (%A)"` and record the output. This is today's authoritative date. If your in-context impression of the date differed, that is drift — treat other in-context impressions of time, intervals, and "last session" as also potentially drifted.
- [ ] For each active project listed in the workspace's `index.yaml`, run `git log -5 --pretty=format:"%h %ai %s" -- projects/<id>/` and read the output. The most recent commit timestamp is the project's verified "last session." Trust this over any cached `last_session` field in CONTEXT.md or `index.yaml`.
- [ ] Cross-check each project's `index.yaml` `last_session` value against git log. If they disagree, the git log wins; update `index.yaml` before proceeding.
- [ ] Invoke the `synthesis-checkpoint` skill on any project whose cached state may be stale — it is the codified protocol for this verification.
- [ ] **Day-end state read (v2.14.0):** read `~/.synthesis/day-end/state.json` and report the last day-end (date + mode) in the day plan's header or brief. If the most recent workday's day-end is missing, say so explicitly — visible skips are recoverable skips. Update `last_day_start` in the same file as part of this ritual.
- [ ] **Weekly-review-owed check (v2.14.0):** if today is on/after the most recent Friday AND `last_weekly_review` predates that Friday, the Weekly Loose-Ends Review is owed — run the Day-End Step 10 scan in THIS session (either ritual direction, any mode) and update `last_weekly_review`. If a `synthesis-catchup-ledger` sweep already ran on/after that Friday, record its date instead of re-scanning — the ledger supersedes the review for its window.

This step is the L2 (skill-rule) anchor of the temporal & continuity discipline. The L1 (Claude Code hooks) and L3 (CLAUDE.md item 13c–13e) reinforce it. See `synthesis-context-lifecycle` Session Start Protocol for the underlying rationale.

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

- [ ] Enumerate the repos to sync. Primary source (v2.13.0): `<workspace>/.agents/repos.yaml` — **every repo with `ritual_sync: yes`, on every run** (skip the whole workspace only if its manifest says `status: dormant`). Fallback when no `repos.yaml` exists: the workspace's `CLAUDE.md` "Workspace Repos" table, every repo marked Yes. Either way the declared list is the complete decision — do NOT re-apply your own judgment about which repos seem "active" (v2.12.1). Context/ai-knowledge repos are marked No and are handled separately (checkpoint-sync / repo-guard).
- [ ] For each repo: `git fetch --all` to pull from all configured remotes, then fast-forward the default branches the team works on (typically `main` + `develop`; some teams also have `staging`, a long-running release branch, etc.). Use `git pull --ff-only` per branch — never a merge or rebase that could introduce silent conflicts.
- [ ] If any branch is **diverged** (local has commits the remote doesn't, AND remote has commits local doesn't), do NOT auto-resolve. Surface it in the day-plan briefing: "develop diverged in `<repo>` — N local commits vs M remote." Decide explicitly: rebase, merge, or leave it for the owner.
- [ ] If a default branch is **behind**, fast-forward it. If it's **ahead** of remote only (local commits not pushed), surface that too — it's a "do I push?" decision, not an auto-action.
- [ ] Report the touched repos with their before/after commit SHAs in the daily plan (e.g., "develop: aaaaaaa → bbbbbbb, 11 commits, includes ticket-id-here"). This gives the user a glanceable view of what arrived overnight.
- [ ] Note any new branches that appeared on remotes (`git branch -r` shows them) — those may be feature branches worth knowing about even if not yet ready for review.

The set of remotes for each repo comes from `git remote -v` inside that repo. The skill does NOT need a separate per-remote config — the repo itself is the source of truth for its own remote layout. When a workspace's primary remote changes (e.g., a migration from one Git host to another), the change happens in the local repo's `git remote -v`, and this step picks it up automatically.

#### 3b. Slack Sync

- [ ] Check for new PRs, CI results, overnight pushes (now that local repos are current).
- [ ] **Run `/synthesis-slack-sync`** — the `synthesis-slack-sync` skill handles the full Slack sync protocol: verify connector auth, read all channels, re-read all threads with replies, check DMs, save to local transcripts, and update the action plan. See that skill for the detailed protocol and the rationale behind each step. Configuration is in `.agents/slack-sync.yaml` per project, with `.claude/slack-sync.yaml` supported for existing projects.
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
- [ ] Check calendar for meetings today and prep needed.
- [ ] Update the action plan throughout the day as tasks complete or change — it is a living document, not a static morning capture.
- [ ] **Always include a clickable link to the action plan file** in your response when creating, updating, or referencing it. Use the absolute path in markdown link format: `[2026-03-23.md](/absolute/path/to/daily-plans/2026-03-23.md)`. Never use relative paths — they don't resolve in the IDE.

### 7. Morning Messages

- [ ] Post standup updates or morning status in relevant channels.
- [ ] Send motivational replies acknowledging overnight work (engineers who feel seen ship faster).
- [ ] Reply to any unanswered threads that need morning response.
- [ ] **Before drafting ANY reply for the user, re-read the actual Slack thread via MCP — not the local transcript.** The user may have already replied. Another team member may have resolved the question. Drafting from stale transcripts makes the user look absent-minded. Transcripts are caches for historical context; Slack is the source of truth for current thread state.
- [ ] **Ground ALL draft messages in actual systems — not just transcripts and meeting notes.** Before drafting ANY reply or message for the user, research the topic in primary sources first. This is not optional and applies to every draft, not just explicitly technical ones. See the Grounding Protocol below.
- [ ] When drafting messages for the user to send manually, ALWAYS include a thread locator: channel name, date/time of parent message, thread timestamp (TS), and the last unanswered reply with date/time and first ~10 words. The user needs this to find the thread instantly.

---

## Grounding Protocol for Draft Messages

Every draft message must be grounded in primary sources before it is written. The depth of research scales with the type of claim being made, but the requirement applies to ALL drafts — not just ones that feel technical.

### Research by question type

| Question type | What to check | Examples |
|--------------|---------------|----------|
| **Technical** (architecture, how something works, root cause) | Source code, config files, PRs, `git log` | "How does X work?", "Why did Y break?" |
| **Status** (what's deployed, what's working) | Deploy scripts, version files, environment config, running services | "Is X on production?", "When was Y released?" |
| **Infrastructure** (secrets, credentials, environments, CI/CD) | Terraform, deploy scripts, `.env.example`, CI/CD workflows, docs | "How do we manage secrets?", "Where does X run?" |
| **Process** (PR workflow, branching, review, release) | Agent instruction files, contributor guides, recent git history, skill files | "What's the merge process?", "Who reviews?" |
| **Product** (feature behavior, user-facing text, prompts) | Component code, prompt YAML files, test files | "Does the tool do X?", "What does the user see?" |

### Investigate First, Ask Questions Later

**Before drafting ANY reply to a bug report or user issue, spend 10 minutes investigating.** Read the relevant code, check the config, search for the pattern. If you can fix it in those 10 minutes, fix it and draft a reply with the fix — not a reply asking for more information.

This principle applies to ALL draft messages that respond to reported problems:

- **Do NOT draft** "Can you share the URL?" when you could search the config and find the missing domain yourself.
- **Do NOT draft** "We're looking into it" when you could have already shipped the fix.
- **Do NOT draft** "Can you try again?" when you haven't investigated the root cause.
- **DO investigate** code, config, logs, and infrastructure before composing a reply.
- **DO fix the problem first** if possible, then draft a reply that leads with the fix.
- **Only ask the user** for information you genuinely cannot obtain yourself (specific reproduction steps, subjective preferences, environment details unique to them).

**Why:** The user's time is more valuable than the agent's. A fix shipped in 10 minutes builds more trust than a reply asking for more info. Action before questions.

**Example:** A user flagged "Import Failed" on certain stories. The initial draft asked for the specific URL. Instead, investigating the config found that a domain was simply missing from the allowed list. The fix took 10 minutes. No round-trip needed.

### The process

1. **Identify the claim.** Before writing, ask: "What factual assertions will this message make?"
2. **Research each claim.** Use Grep, Read, Glob, git log, or other tools to find the primary source.
3. **Note the evidence.** Record file paths, line numbers, config values, or PR numbers that support the claim.
4. **Draft with citations.** Include specific references where they add credibility (e.g., "We use GCP Secret Manager — see `terraform/modules/secrets/main.tf`").
5. **Flag uncertainty.** If a claim can't be fully verified, say so in the draft rather than guessing.

### Why this matters

The user's professional reputation depends on accuracy. A wrong technical claim in Slack is visible to the entire team and cannot be unsent. A delayed but accurate response is always better than a fast but wrong one.

**Incident (2026-03-17):** A technical reply was drafted based on conversation memory alone. It was partially wrong. The next day, another reply was drafted after reading the actual code — it was fully correct. The difference was 5 minutes of research.

### Scope

This protocol applies everywhere draft messages are created:
- Morning messages (Day-Start Step 7)
- Mid-day sync replies (synthesis-slack-sync Step 5)
- End-of-day communications (Day-End Step 3)
- Ad-hoc message requests throughout the day

---

## Draft Message Formatting Rules

All draft messages in the daily action plan must follow these formatting and quality rules. The user copy-pastes these directly into Slack — formatting errors waste time and look unprofessional.

### Slack Formatting

1. **Blank line after every bullet.** Slack requires a blank line between bullet points for them to render as separate items. Without blank lines, bullets collapse into a single paragraph. This is the most common formatting error — check every draft before saving.

   **Wrong (collapses in Slack):**
   ```
   • Item one
   • Item two
   • Item three
   ```

   **Right (renders as separate bullets):**
   ```
   • Item one

   • Item two

   • Item three
   ```

2. **Use Slack markdown, not GitHub markdown.** Slack uses `*bold*` not `**bold**`. Use `_italic_` not `*italic*`. Use `>` for blockquotes. Use `` `code` `` for inline code.

3. **Thread locators for every reply draft.** Include: channel name, human-readable date/time of parent message, author name, and first ~10 words of the message being replied to. Use the format: `**Channel:** #channel-name — Author Name, Mon Mar 30 at 11:31 AM EDT — "First ten words of the message..."`. The Slack thread TS (Unix timestamp) should be included for technical reference but is NOT the primary locator — the human-readable context is what the user needs to find the thread.

4. **Keep messages concise.** Slack messages over ~15 lines get collapsed behind a "Show more" fold. Front-load the most important information.

### Draft Numbering Convention

Drafts in a daily plan are labeled with sequential integers, not alphabet letters. The first draft of the day is **Draft 1**; each subsequent draft increments by 1.

**Do:**

- `### Draft 1: Multi-provider routing announcement`
- `### Draft 2: Reply to Oliver — Terraform readiness`
- `### Draft 11: Patrick public praise — release window`
- `### Draft 12: User-channel supplement (L&E)` (when same theme is routed to multiple audiences, each variant still gets its own integer)

**Do NOT:**

- `### Draft A: ...`, `### Draft B: ...` (alphabet labels — replaced by integers in v2.6.0)
- `### Draft K-2: ...`, `### Draft K-3: ...` (letter-with-suffix sub-versioning — replaced by sequential integers)

**Pre-draft step:** before adding a new draft, grep or scan the file for the highest existing `Draft N` integer and use N+1.

**Retraction:** if a draft is retracted (e.g., a fabricated message caught and removed), keep the number reserved in the file (`### Draft N — retracted` with a one-line pointer to the session log) rather than renumbering subsequent drafts. The reserved slot is the durable historical record.

See the v2.6.0 section at the top of this skill for the full rationale (counting tax, lexicographic ordering, sub-version ugliness, cross-file consistency).

### Temporal Integrity

Every draft message must be accurate *at the time it will be sent*, not at the time it was written. This is the most common source of anachronistic messages.

**Before finalizing each draft, check:**

1. **Has the recipient already received this information?** If the same person was tagged in an earlier message or was present at a meeting where this was discussed, don't repeat it. Restructure the message to cover only what's new or what still needs their input.

2. **Do forward-looking statements match reality?** "Will review next" is a commitment. "Staging is ready for QA" is stale if QA already started. "Welcome back" is odd if the person was just in a meeting with you. Audit every verb tense.

3. **Are scheduled-for-later messages written in the right tense?** A message drafted Monday but scheduled for Tuesday must say "yesterday" not "today" when referencing Monday events. The easiest way to catch this: read the message as if you are the recipient reading it at the scheduled send time.

4. **Does the message acknowledge what happened since it was drafted?** If a standup, deployment, or Slack conversation happened between drafting and sending, re-check the message. Information that was "upcoming" may now be "completed."

5. **Has the topic moved to another channel or medium?** Obsolescence is cross-channel and cross-medium: a Slack question may have been answered in email, a meeting, or a different channel entirely. Before sending, sweep recent transcripts across ALL synced surfaces for the recipient + topic, and search email when the subject could plausibly have crossed mediums. For email replies, always re-pull the FULL thread first — the latest message may supersede the one being answered. Drafts older than 24 hours get full fact re-verification, not just a thread re-read. (Agent-assisted send paths should enforce this as a mandatory send-time gate — see the user's send-system skill if one exists.)

**Common temporal integrity failures:**
- "Welcome back" to someone who was at the meeting you just attended together
- "Staging is ready for QA" sent to someone who was already tagged in a staging notification
- "Good that you're meeting with X today" in a message scheduled for tomorrow
- "I'll review this next" when you've already moved on to other work

### Grounding Verification Checklist

Before finalizing each draft message, verify:

- [ ] **Every technical claim cites a source** — file path, line number, PR number, config value, or git SHA.
- [ ] **Every status claim is current** — verified against the actual system state (git log, deploy status, environment), not just memory or transcripts.
- [ ] **Every attribution is correct** — the right person is credited for the right work. Cross-reference PR authors via `gh pr view` or `git log`, not memory.
- [ ] **No stale information — checked beyond the thread.** Re-read the target thread via MCP to confirm no one has replied or resolved it, AND sweep for the topic across OTHER channels, DMs, and email — resolutions frequently happen outside the thread where the question was asked. A message rendered obsolete by a communication anywhere is obsolete everywhere.
- [ ] **Numbers are accurate** — test counts, file counts, line counts, character counts are from actual tool output, not estimates.
- [ ] **Temporal integrity passes** — message is accurate at the time it will be read, not just at the time it was written. See Temporal Integrity section above.

### Pre-Send Review Gate

Every draft message section in a daily plan must include the following notice before the first draft:

> **Review before sending.** These drafts are grounded in real data — code commits, test results, deployment logs, Slack threads, and project context — but they are starting points, not final messages. Read each one, edit it in your own voice, and add the personal touch only you can. Human-to-human communication deserves human effort.

This is not optional. Draft messages are research-backed starting points — not automated communications. The human must:
1. Read each draft fully before sending
2. Edit the tone and phrasing to match their voice
3. Add personal context that only they have (relationship nuance, recent conversations, political awareness)
4. Verify the message is appropriate for the current moment (not just factually correct)

The grounding section shows the research behind the draft. The human adds the judgment, timing, and personal touch that make the message authentic.

### Appreciation Message Quality

Appreciation messages must be specific and grounded, not generic. Each should reference:
- The specific work product (PR number, feature name, article title)
- What made it good (thorough test plan, clean architecture, consistent output, specific design decision)
- Observable impact (unblocks X, addresses user feedback Y, improves process Z)

**Generic (weak):** "Great work on the PR, Emil!"
**Grounded (strong):** "Emil — PR #96 was clean with solid UUID validation and 6 permission tests covering all access paths. The immediate user sync on org assignment was the right architectural call — avoids the confusion of next-login delays."

---

## Daily Plan Structure: Preserve and Reorganize

The daily action plan is both a **live dashboard** (scannable current state) and a **historical record** (what happened today). These goals conflict if the file is treated as append-only — by evening, sections are scattered and duplicated, making the file unreadable.

### The Rule: Preserve All Information, Reorganize for Clarity

**Never delete information.** Completed tasks, sent messages, timestamps, decisions, and resolved items must always be preserved somewhere in the file.

**Reorganize freely.** Consolidate scattered sections, merge duplicate lists, reorder for readability. The file should have ONE section for each concern, not multiple sections that accumulated through the day. After every sync or major update, the file should read cleanly from top to bottom.

### Required File Structure (v2.4.0+)

The daily plan follows this canonical structure. On each update, consolidate into these sections rather than appending new ones. The synthesis-console v0.8+ cockpit parses these section names to typed regions; staying within the canonical vocabulary maximizes the typed UI surface.

```markdown
# Daily Action Plan — [Day], [Date]

**[Status line: version, key people, blockers]**

---

## Decisions needed from Rajiv     ← cockpit: NEEDS YOU region
[H3 question per decision. Each H3 may have **Option A:** / **Option B:** lines
 and a **Recommendation:** line. The cockpit renders option buttons that record
 a `**Decided:** Option X — <ISO>` marker back to the file on click.]

## Priority Tasks                  ← cockpit: TODAY region
### Do today — not negotiable      ← collapsible bucket (P0, expanded by default)
1. **Task title** — description    ← cockpit renders as checkbox; click writes
                                       `~~**Title**~~ ✅ **DONE HH:MM TZ**` in place

### Do today — should make it      ← P1 bucket (collapsed by default)
### Do today — can slip            ← P2 bucket
### Watch / waiting                ← muted styling
### Stale targets                  ← muted styling

## Drafts — Ready to Send          ← cockpit: DRAFTS region
> **Review before sending.** [Standard reviewer notice — keep verbatim.]

### Draft A — [Description]
**Send to:** `#channel-name` — [thread locator]
```
[message body in fenced code block — use 3 backticks if the body has no internal code blocks; use 4 backticks (````) if the body contains any internal ``` blocks. See v2.5.0 — Draft Fence Convention.]
```
**Grounding:**
- [bullet]
- [bullet]

## Standup Highlights              ← cockpit: lower-row collapsible (context tone)
## What Happened Yesterday         ← cockpit: lower-row collapsible (briefing)
## Things to Know                  ← cockpit: lower-row collapsible (briefing)
## Mid-day Sync                    ← cockpit: lower-row collapsible (briefing)
## Waiting On Others               ← cockpit: lower-row collapsible (waiting tone)
## Open PR Queue                   ← cockpit: lower-row collapsible
## Sent Messages                   ← cockpit: lower-row collapsible (done tone)
## Completed Today                 ← cockpit: lower-row collapsible (done tone)
## Sync state                      ← cockpit: lower-row collapsible
## Bugs (Open)                     ← cockpit: lower-row collapsible (briefing)
## Carried Items                   ← cockpit: lower-row collapsible (briefing)
```

### Canonical Section Vocabulary (Authoritative)

The synthesis-console v0.8+ parser classifies each H2 heading into one of these kinds. Use the canonical name where possible. The "synonyms" column lists variants the parser also recognizes via substring + case-insensitive match — these exist for backward compatibility but new plans should prefer the canonical name.

| Cockpit region / kind | Canonical H2 name | Recognized synonyms |
|----------------------|-------------------|---------------------|
| **decisions** (NEEDS YOU) | `Decisions needed` | "Decisions to make", "Open ask", "Asks for Rajiv", "Open Items", "Needs your attention", "Open Quality Concerns" |
| **priority-tasks** (TODAY) | `Priority Tasks` | "Tasks", "Tasks for Rajiv", "Tasks Today", "Today's Tasks", "Today's Priorities", "Still To Do", "This Week", "Remaining Tasks", "Pending This Session", "Pending from Before Vacation" |
| **drafts** (DRAFTS) | `Drafts — Ready to Send` | "Drafts", "Unsent — Ready to Send", "Unsent Drafts", "DM Reply Drafts", "Draft Messages", "Messages", "Next Steps", "Pending Emails", "Scheduled for Tomorrow / Later" |
| **standup** | `Standup Highlights` | "Standup Transcript", any heading with "standup", "Newsroom Training" |
| **sent-messages** | `Sent Messages` | "Messages Sent" |
| **waiting** | `Waiting On Others` | "Waiting on", "Delegated to Team" |
| **pr-queue** | `Open PR Queue` | "PR Queue", "Open PRs", "New PRs", "PRs Ready for Review", "PR Reviews Completed" |
| **sync-state** | `Sync state` | "Staging/Deployment Status", "Deployment Status", "Pre-Migration Status", "Post-Release Status", "Files Created/Modified", "Test Results", "Staging:" |
| **completed** | `Completed Today` | "Completed This Morning" |
| **briefing** | `Things to Know` | "What Happened", "What Changed", "Big Things", "Things Rajiv Should Know", "Carried From / Items / Forward", "Carry Forward", "Mid-day Sync", "Morning Sync", "From Slack Sync", "State Catch-Up", "Day Summary", "End of Day Summary", "Bugs (Open)", "QA Findings", "QA Results", "CRITICAL:", "Context", "What to Watch", "Future Work", "Post-Release Issues", "Feature Requests (Carryover)", "Release Process Sync" |
| **other** (fallback) | (any unrecognized H2) | Renders as plain markdown in the lower-row collapsibles. Nothing is lost; the section just isn't specially typed. |

### Internal Structure Conventions

Within each section, the parser also recognizes structural patterns. Adhering to these makes the UI work correctly:

**Decisions section** (`## Decisions needed`):
- One H3 per decision (`### 1. Force-push origin/develop?`)
- Options as bold paragraphs: `**Option A:** description`, `**Option B:** description`
- Optional: `Recommendation: **A** with rationale`
- After click: skill / human appends `**Decided:** Option X — <ISO>` directly under the H3
- **Synthetic asks**: an H2 like `## Open ask for Rajiv` with prose body and NO H3s also surfaces in NEEDS YOU as a single card with the prose verbatim. Use this for one-off requests that don't fit the A/B/C structure.

**Priority Tasks section** (`## Priority Tasks`):
- One H3 per bucket (`### Do today — not negotiable`)
- Tasks as numbered list items (`1. **Title** — description`) OR checkbox items (`- [ ] **Title** — description`). Both formats supported.
- Already-done tasks may be marked any of these ways (parser detects all): `~~Title~~ ✅ DONE HH:MM`, `[x]`, leading `✅`, leading `DONE` or `SENT`.
- The cockpit's TODAY region surfaces tasks as live checkboxes that write the canonical done marker back to the file on click.

**Drafts section** (`## Drafts — Ready to Send`):
- One H3 per draft (`### Draft A — Description`)
- A `**Send to:** target — locator` paragraph identifying the recipient. `**Channel:**` is also accepted.
- A fenced code block OR blockquote with the message body. **Fence convention (v2.5.0+):** default is 3 backticks; if the body contains any internal triple-backtick code blocks (install commands, log excerpts), use a 4-backtick outer fence (or any length strictly greater than the longest internal fence). The 4-backtick outer fence renders correctly in synthesis-console AND survives the Copy button intact (outer fence stripped, inner ` ``` ` preserved for Slack to re-interpret).
- Optional: a `**Grounding:**` paragraph or bullet list with research backing.
- After send: skill / cockpit appends `**Sent:** <ISO> (TS=...) <permalink>` directly under the body.
- **Drafts may also appear under non-drafts H2s.** When a draft is added to a topical context (e.g., a draft DM written into "Things to Know" alongside the situation that prompted it), the cockpit's DRAFTS region aggregates it from wherever it lives in the document. The canonical placement is still under `## Drafts`, but topical inline drafts work too.

**Pre-Send Review Notice**: every drafts H2 SHOULD include this verbatim blockquote before the first H3 draft (the cockpit doesn't currently re-display it in the DRAFTS region but it remains in the file for archival and Full-Markdown view):

```
> **Review before sending.** These drafts are grounded in real data — code commits, test results, deployment logs, Slack threads, and project context — but they are starting points, not final messages. Read each one, edit it in your own voice, and add the personal touch only you can. Human-to-human communication deserves human effort.
```

### What This Means in Practice

- When a draft is sent: move it from "Unsent" to "Sent Messages" with a timestamp. Don't create a new "More Sent Messages" section.
- When a bug is resolved: update the entry in "Bugs" to show it's resolved. Don't leave the old entry and add a new one elsewhere.
- When a sync finds new info: update the relevant existing section. Don't append a new section for each sync.
- When the file gets messy: do a full rewrite that preserves all information in the canonical structure. This is expected and encouraged — it's maintenance, not data loss.

### Why This Replaced "Append-Only"

The original "append-only" rule was designed to prevent accidental deletion of sent message records. The intent was correct — losing records causes duplicate sends and confusion. But in practice, append-only caused the file to balloon with scattered duplicate sections ("More Sent Messages (afternoon)", "More Sent Messages (afternoon, continued)", "Unsent — Ready to Send", "Unsent — Evening"), becoming unreadable by end of day.

The preserve-and-reorganize approach achieves the same safety goal (no information loss) while maintaining readability. The transcript files (`{workspace}/channels/YYYY-MM-DD.md`, `{workspace}/dms/YYYY-MM-DD.md`, `{workspace}/group-dms/YYYY-MM-DD.md`) are the authoritative append-only historical records. The daily plan is the dashboard.

### File Revert Protection

If a file revert is detected (system reminder says "file was externally modified"):
1. Re-read the ENTIRE file from disk before making any edits.
2. Compare the on-disk content against your in-memory understanding of the file.
3. If content is missing (items you know were written earlier are gone), reconstruct the missing content from Slack sync data, session memory, and transcript files.
4. Never silently accept a reverted file — always verify and restore.

---

## Mid-Day Sync Protocol

The day-start checklist does a full sync. The user will ask for syncs repeatedly throughout the day ("sync from Slack", "what's new", "check channels").

**Run `/synthesis-slack-sync`.** The `synthesis-slack-sync` skill handles the complete protocol: read channels, re-read all threads with replies, check DMs, save to local transcripts, and update the action plan. See that skill for the detailed five-step protocol.

The key discipline encoded in that skill: **every sync must re-read ALL threads with replies from today**, not just fetch new channel-level messages. Thread replies don't appear as channel messages — skipping thread re-reads causes stale action plans and duplicate message sends.

**Commit after every sync.** Any sync that creates or updates transcript files, daily plans, or context files must commit and push those changes in the same invocation. See the "Commit Protocol" section below. Do not defer to day-end — the day-end checklist may not run on a given day, and the value of the transcript is lost if it never reaches the remote.

---

## Vacation / Observer Mode Ritual

Use this variant when the user signals they are not actively working ("I'm on vacation", "observer mode", "just keeping up", "don't want to send messages"). Common phrasings: "do the modified ritual", "do what you did the last few days", "stay in observer mode".

Observer mode is NOT a reduced-effort version of the day-start checklist. It is a specific pattern that combines sync + context + commit WITHOUT the active-work steps.

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
6. **Commit and push** all files touched in this invocation. See Commit Protocol below. Scope strictly to the repos where files were actually modified.

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
- **Commit and push in the same invocation** — this is the most commonly missed step in modified rituals. Observer mode does not commit less than active mode; it commits exactly the same.

### Why This Is Codified

When observer mode is reinvented per conversation ("do the thing you did yesterday"), the agent makes judgment calls about which steps matter. The commit step is the most often dropped because it feels like a day-end concern. This skill now states explicitly: commit-and-push is part of every observer-mode invocation, not a deferred step.

---

## Day-End Checklist

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
- [ ] Update CONTEXT.md to mark any items resolved by day's conversations (so tomorrow's day-start does not re-propose them).

### 2. Source-Code Sync

End-of-day code sync ensures local main/develop reflects everything that landed during the day and that tomorrow's day-start begins from a clean, current state. Run the same source-code sync as Day-Start Step 3a — same workspace repo list, same fetch + fast-forward semantics, same surfacing of divergence.

- [ ] For every repo the workspace manifest marks for sync (`<workspace>/.agents/repos.yaml` `ritual_sync: yes`; fallback: the `CLAUDE.md` table's Yes rows — the complete set, no activity judgment; v2.12.1/v2.13.0): `git fetch --all`, then `git pull --ff-only` on each long-running branch (typically `main` and `develop`).
- [ ] Surface any branches that are diverged or have local-only commits not yet pushed. These are decisions to make NOW, not at next day-start, so the agent can act on them while context is fresh.
- [ ] Note the day's net change per repo (e.g., "develop +11 commits, includes ticket-id-here"). This summary becomes part of the day-end log and feeds tomorrow's day-start briefing.

This step is intentionally not "merge ready PRs" — that's Integration Sweep below. This step is pure sync: pull latest state, surface divergence, do not modify history.

### 3. Integration Sweep

- [ ] Check PR queue — merge any ready PRs, push to staging.
- [ ] Close GitHub PRs with integration comments (if using adopt-and-adapt pattern).
- [ ] If a new version was deployed to staging or production, follow your team's release notification process. Best practice: list all PRs included, credit all contributors by name and PR number, post to both product and engineering channels.

### 4. Communications — the send-or-release pass (v2.14.0)

- [ ] Collect today's decay-tagged drafts (every `**Decays:**` line in today's plan) plus unanswered threads from today.
- [ ] For each item, one of three outcomes — nothing decay-tagged carries silently past its date: **send now** (with the user's one-tap approval; nothing sends without them), **re-date** with a stated reason on the Decays line, or **release** (strike through with a one-line why).
- [ ] Post end-of-day status updates; send appreciation for the day's contributions (grounded per the Appreciation Message Quality rules).
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

**Date discipline (matches Day-Start Step 1 and CLAUDE.md item 13c–13e).** All session-log entries and CONTEXT.md updates written tonight MUST use today's verified date — not a date inferred from session continuity or memory. If the conversation has been running for multiple days, the AI's sense of "today" may be wrong by hours or days. Re-anchor before writing.

- [ ] Run `date "+%Y-%m-%d %H:%M:%S %Z (%A)"` once at the start of this step. Use the output as today's authoritative date for every file write that follows. (If `synthesis-checkpoint` is loaded, invoke it instead — it does this anchoring plus a git-log cross-check.)
- [ ] For each project worked on today: append a session-log entry to `sessions/YYYY-MM.md` with today's verified date in the header. Format the date as ISO `YYYY-MM-DD` (e.g., `## 2026-05-27 (Wed) — Day-end summary`).
- [ ] Update CONTEXT.md with day's progress and new state. Refresh the "Last session" field with today's verified date. Update "Recent Sessions" with a one-line summary.
- [ ] Update MEMORY.md if current state info is stale (version numbers, environment status, team assignments).
- [ ] Update `last_session` date in `index.yaml` for each active project worked on today — use today's verified date.
- [ ] Commit context changes per the Commit Protocol below — separate commit per logical group (project context updates, lessons learned, etc.). Use `git add <specific-files>`, NOT `git add -A`.
- [ ] **Push and verify.** Run `git push` for each modified repo, then run `git log origin/main..HEAD` to confirm the local HEAD reached origin. If the output is non-empty, the push did not land — investigate (network failure, branch protection rule, merge conflict) and re-push. Do NOT assume "git push said success" means the commits are durable on the remote.
- [ ] Push updates to any shared ai-knowledge repos if modified. Same push-verify step applies.
- [ ] **Write the day-end state (v2.14.0):** update `~/.synthesis/day-end/state.json` (atomic temp+rename) and append one line to `~/.synthesis/day-end/history.jsonl` — date, ritual direction, mode, outcome, and the send-or-release counts. Every mode writes state, observer included; day-start rituals update their own fields the same way.

### 8. Skills Maintenance

- [ ] If any installed skill copies changed, check whether those edits need to be synced back to the source repo. Use `synthesis-skills-manager` or check `.source.json` provenance files.
- [ ] If skills were updated in source repos, verify they were installed to the Claude Code, Codex, and cross-agent locations that use them.

### 9. Machine Sync

- [ ] Run mac-sync (credentials, config, git remotes across machines).

### 10. Weekly Loose-Ends Review (owed weekly — v2.14.0)

**Owed-weekly gating (replaces the v2.8.0 Friday-only rule).** The review is owed once per week, anchored to Friday, and tracked in `~/.synthesis/day-end/state.json`. Read `last_weekly_review`: if it is on/after the most recent Friday, skip this step silently. If it predates the most recent Friday and today is on/after that Friday, run the scan below — in whichever ritual notices first (Day-Start Step 1 checks the same condition), in any day-end mode including Quick Close — then update `last_weekly_review`. A `synthesis-catchup-ledger` sweep on/after that Friday counts as the week's review (record its date); and if this scan finds 2+ consecutive missed rituals, suggest running that skill — it is the recovery tool for broken cadence. This decoupling exists because a Friday-evening-only review is disabled by exactly the skip it is meant to catch.

This step exists because work falls through the cracks during a week. A missed close-of-business ritual means the next day's plan doesn't pick up the open threads from the day before. By Friday, several items can be stranded invisibly. The Friday review catches these BEFORE the weekend disconnects fresh context, and assembles a clean carryover list for Monday.

**Scope: past 14 calendar days.** Look back from today through 14 days ago. This captures the current week + the previous week — enough to surface items deferred across one weekend boundary, which is the typical failure mode.

**Sources to scan (read each one; do not infer):**

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
- [ ] Commit + push the daily plan and any annotated source files per the Commit Protocol below.

**Failure mode to avoid:** writing a `## Weekly Loose-Ends Review` section header without actually scanning the sources. The value is in the scan. If sources have not been read in this invocation, do not write the section — note "Weekly Loose-Ends Review skipped — scan not performed this invocation" in the plan and surface the gap to the user.

**Idempotency:** if a Friday review was missed and the agent runs this step on a later weekday, the scan still works because it's date-bounded (past 14 calendar days from today), not weekday-bounded. The Friday-default is about WHEN it normally fires; the scan output is meaningful on any day.

### 11. Repo Guard — Final Verification

**This step is mandatory and must be the last step before ending any session.**

- [ ] Run `repo_sync_check.py` (from `synthesis-repo-guard` skill) across the full workspace.
- [ ] If ANY repos are dirty or unpushed, resolve them before ending: commit and push, or explicitly decide to discard.
- [ ] Zero untracked files, zero uncommitted changes, zero unpushed commits. No exceptions.

This is not the same as steps 7-9. Those steps commit specific known changes. This step is the **verification gate** that catches anything those steps missed — files from earlier in the session, changes in repos you forgot about, installed skill copies that were changed without source updates. The gate must pass before the session ends.

---

## Commit Protocol — Apply to Every Ritual Invocation

Every ritual invocation — day-start, mid-day sync, day-end, or observer mode — must commit and push any context, transcript, plan, or reference files it modifies. This is not deferred; it happens at the point of modification.

### Scope Rule: Only Commit Repos Touched in This Invocation

This is a hard rule to prevent unintended commits of unrelated work:

1. **Track** which files this invocation created or modified. The agent's own action history is the source of truth — do not infer scope from `git status`, which may include unrelated work in progress.
2. **Group** those files by their containing repo.
3. **For each repo touched:** `git add <specific files>` (never `git add -A`, never `git add .`), then commit, then push.
4. **Never touch** repos where this invocation did not create or modify files, even if they are dirty. That work belongs to another session.

**Example:** A daily ritual for Project A updates `projects/project-a/CONTEXT.md` and creates `daily-plans/YYYY-MM-DD.md`. If the user also has uncommitted work in `projects/project-b/` from a different session, the ritual does NOT commit that. Only the files this invocation touched.

### Pre-Commit Hook Failures

If a pre-commit hook flags sensitive content:
- If the destination repo is PRIVATE and the content is intentional (shared reference docs, meeting transcripts, strategic planning copies), use `git commit --no-verify` only after confirming with the user.
- If the destination repo is PUBLIC, stop. Sanitize the content or exclude the file. Never bypass hooks to push sensitive content to a public repo.
- If the content is unexpectedly sensitive (credentials, tokens, personal data leaked into a config), investigate before deciding. Do not commit.

### Commit Message Standards

- Reflect the actual changes ("Project week N: context, daily plans, transcripts") not generic filler ("Update files").
- For private repos, be specific. For public repos, use generic messages that don't reveal restricted names, article titles, or client-specific details.
- Include `Co-Authored-By` trailer when appropriate.

### Verification Is Separate from Commit

`synthesis-repo-guard` is a **detector** across the workspace — it reports dirty repos. It is NOT a committer. Use it as a final verification gate at session end to catch anything missed, not as the primary commit mechanism.

---

## How to Create a Project Supplement

Project supplements live in `daily-plans/` (shared infrastructure). Example: `daily-plans/daily-checklists.md`. Each project MAY also keep project-specific ritual notes in its own directory if they don't apply cross-project. The supplement should contain:

1. **Repos to sync** — which repos to `git fetch --all` on
2. **Channels to sync** — specific Slack channels and DMs with IDs
3. **PR review targets** — GitHub/Bitbucket repos to check for pending PRs
4. **Stakeholder comms** — who to message and in what channels
5. **Project-specific end-of-day** — any project-specific cleanup (mirror pushes, staging verification, etc.)

The project supplement is referenced from the global checklist at "Run any project-specific sync steps."

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

---

## Principles Behind These Checklists

- **Dependency-ordered:** Each step feeds the next. Sync before reading. Read before planning. Plan before messaging.
- **Information entropy reduction:** The primary purpose is closing the gap between what happened and what you know.
- **Human investment:** Motivational messages are not optional — they are a force multiplier on a distributed team.
- **Career compounding:** Every day produces raw material for thought leadership. The discipline is noticing it.
- **State capture:** If you do not capture today's state, tomorrow's start takes longer. This compounds.
