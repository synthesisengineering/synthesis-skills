---
name: synthesis-daily-rituals
description: "Day-start and day-end checklists for synthesis engineering projects. Execute dependency-ordered rituals for context optimization, Slack sync, catch-up reads, PR reviews, day planning, and communications. Use when asked about: daily ritual, morning routine, day start, day end, daily checklist, morning checklist, end of day checklist, daily workflow."
license: "Apache-2.0"
depends_on:
  - synthesis-context-lifecycle
  - synthesis-project-management
  - synthesis-slack-sync
  - synthesis-repo-guard
metadata:
  author: "Rajiv Pant"
  version: "2.3.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Daily Rituals — Global Checklists

Standard day-start and day-end rituals for synthesis engineering projects. These are the global (per-person) checklists. Each project may have a project-specific supplement that extends these with channel-specific sync, repo-specific checks, and stakeholder-specific communications.

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
| `slack_auth_command` | `claude mcp auth slack` | Command to re-authenticate Slack MCP |

---

## Day-Start Checklist

Execute in this order (each step depends on the one before it).

### 1. Context Optimization

**Archive FIRST, delete second. Never remove content from CONTEXT.md until it exists in its destination (sessions/ or REFERENCE.md). Two-phase commit.**

- [ ] Check CONTEXT.md line count for each active project. If >120 lines, archive before starting work.
- [ ] Archive completed items and old session summaries to `sessions/YYYY-MM.md` FIRST.
- [ ] Archive any newly-stable facts to REFERENCE.md FIRST.
- [ ] Verify archived content exists in destination files.
- [ ] Only then rewrite CONTEXT.md with archived content removed.
- [ ] Update `last_session` date in `index.yaml`.

### 2. Sync

- [ ] `git fetch --all` on all active project repos.
- [ ] Check for new PRs, CI results, overnight pushes.
- [ ] **Run `/synthesis-slack-sync`** — the `synthesis-slack-sync` skill handles the full Slack sync protocol: verify MCP auth, read all channels, re-read all threads with replies, check DMs, save to local transcripts, and update the action plan. See that skill for the detailed protocol and the rationale behind each step. Configuration is in `.claude/slack-sync.yaml` per project.
- [ ] Run any project-specific sync steps (see project supplement).

### 2b. Meeting Transcripts

After any standup, planning session, or design review with auto-generated notes (e.g., Gemini in Google Meet):

**Automated path (preferred)** — if the project uses `synthesis-meeting-transcripts`:
- [ ] **Run `/synthesis-meeting-transcripts`** — the skill searches Gmail/Drive for today's Gemini-generated meeting notes doc, fetches both the summary and the full word-for-word transcript, and saves to `~/workspaces/{workspace}/ai-knowledge-{workspace}-rajiv-private/transcripts/meetings/`. Configuration in `.claude/meeting-transcripts.yaml` per project. Works with Anthropic's hosted Gmail/Drive connectors (single account) or a self-hosted multi-account MCP.
- [ ] Read the saved transcript and extract action items, decisions, status changes.
- [ ] Update CONTEXT.md with any new information from the meeting.

**Manual path (fallback)** — if no Gmail/Drive tooling is available:
- [ ] Download transcript from `~/Downloads/`.
- [ ] **Verify transcript completeness.** Check that the file contains BOTH a summary/notes section AND a full conversation transcript (speaker-attributed dialogue with timestamps). Many AI note-takers (Gemini, Otter, Fireflies) produce a summary by default but may omit the raw transcript. **If the file contains only a summary without the full transcript log, warn the user immediately** — the raw transcript is the primary source; summaries are lossy and may misattribute or omit statements.
- [ ] Move to workspace meetings directory (`~/workspaces/{workspace}/ai-knowledge-{workspace}-rajiv-private/transcripts/meetings/`) with naming convention: `standup-YYYY-MM-DD.md` or `meeting-TOPIC-YYYY-MM-DD.md`. The `{workspace}` value comes from the project's `.claude/slack-sync.yaml` config.
- [ ] Read transcript and extract action items, decisions, status changes.
- [ ] Update CONTEXT.md with any new information from the meeting.

### 3. Catch-Up Read

**Cross-check before proposing action. An item that looks open in CONTEXT.md may already be resolved in Slack (or vice versa). The source of truth is the actual thread, not the action item list.**

- [ ] Review synced transcripts (`{workspace}/channels/`, `{workspace}/dms/`, `{workspace}/group-dms/` for today) and new messages for anything requiring action or awareness.
- [ ] For each potential action item: check the thread for replies, check CONTEXT.md for prior completion, check session logs. Only flag as open if ALL sources confirm it's unresolved.
- [ ] Note new action items, status changes on waiting items, and signals worth responding to.
- [ ] Remove or mark completed any CONTEXT.md items that Slack evidence shows are resolved.

### 4. PR Review Queue

- [ ] Check for PRs awaiting your review (lead integration review or peer review).
- [ ] Note age of oldest pending PR — anything >2 days old is a bottleneck.

### 5. Day Plan

- [ ] **Review yesterday's daily plan** (`daily-plans/YYYY-MM-DD.md`). Identify: uncompleted tasks to carry forward, draft messages that were never sent, items that are now stale due to overnight Slack activity, and "waiting on others" items that may have been resolved.
- [ ] **Cross-reference yesterday's plan with today's Slack sync.** A task marked incomplete yesterday may have been resolved overnight. A draft message from yesterday may no longer be accurate due to code changes, PR merges, or Slack replies. Do not blindly carry forward — verify each item is still valid and current.
- [ ] Create today's action plan in `daily-plans/YYYY-MM-DD.md` (shared infrastructure, not inside individual project directories or ~/Downloads). This creates a permanent archive.
- [ ] The action plan should contain: tasks (prioritized with checkboxes), draft messages (with thread locators), things to know, waiting-on-others table, and everything else.
- [ ] Update CONTEXT.md action items with new items from catch-up.
- [ ] Prioritize today's work: integration, reviews, communications, features, meetings.
- [ ] Check calendar for meetings today and prep needed.
- [ ] Update the action plan throughout the day as tasks complete or change — it is a living document, not a static morning capture.
- [ ] **Always include a clickable link to the action plan file** in your response when creating, updating, or referencing it. Use the absolute path in markdown link format: `[2026-03-23.md](/absolute/path/to/daily-plans/2026-03-23.md)`. Never use relative paths — they don't resolve in the IDE.

### 6. Morning Messages

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
| **Process** (PR workflow, branching, review, release) | CLAUDE.md, contributor guides, recent git history, skill files | "What's the merge process?", "Who reviews?" |
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
- Morning messages (Day-Start Step 6)
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

### Temporal Integrity

Every draft message must be accurate *at the time it will be sent*, not at the time it was written. This is the most common source of anachronistic messages.

**Before finalizing each draft, check:**

1. **Has the recipient already received this information?** If the same person was tagged in an earlier message or was present at a meeting where this was discussed, don't repeat it. Restructure the message to cover only what's new or what still needs their input.

2. **Do forward-looking statements match reality?** "Will review next" is a commitment. "Staging is ready for QA" is stale if QA already started. "Welcome back" is odd if the person was just in a meeting with you. Audit every verb tense.

3. **Are scheduled-for-later messages written in the right tense?** A message drafted Monday but scheduled for Tuesday must say "yesterday" not "today" when referencing Monday events. The easiest way to catch this: read the message as if you are the recipient reading it at the scheduled send time.

4. **Does the message acknowledge what happened since it was drafted?** If a standup, deployment, or Slack conversation happened between drafting and sending, re-check the message. Information that was "upcoming" may now be "completed."

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
- [ ] **No stale information** — if referencing a thread, re-read it via MCP to confirm no one has already replied or resolved it.
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

### Required File Structure

The daily plan should always follow this canonical structure. On each update, consolidate into these sections rather than appending new ones:

```markdown
# Daily Action Plan — [Day], [Date]

**[Status line: version, key people, blockers]**

---

## Completed Today
[Single consolidated list of everything done, in chronological order]

## Staging/Deployment Status
[Current state of staging and production]

## Sent Messages
[ALL sent messages in one section, chronological, with timestamps and TSs]

## Unsent — Ready to Send
[ONLY messages not yet sent. Remove from here and move to Sent when sent.]

## Scheduled for Later
[Messages for tomorrow or future days]

## Standup Highlights
[Standup summary — written once, not duplicated]

## QA Findings
[Consolidated QA results — updated in place, not appended]

## Priority Tasks (Remaining)
[Only uncompleted tasks. Completed tasks move to "Completed Today".]

## Carried Items
[Items deferred to tomorrow or beyond]

## Bugs (Open)
[Single consolidated bug list — updated in place]

## Waiting On Others
[Single table — updated in place]
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

### 1. Transcript Sync

- [ ] **Run `/synthesis-slack-sync`** for final capture of the day. The `synthesis-slack-sync` skill ensures all channels, threads, and DMs are captured.
- [ ] Update CONTEXT.md to mark any items resolved by day's conversations (so tomorrow's day-start does not re-propose them).

### 2. Integration Sweep

- [ ] Check PR queue — merge any ready PRs, push to staging.
- [ ] Close GitHub PRs with integration comments (if using adopt-and-adapt pattern).
- [ ] If a new version was deployed to staging or production, follow your team's release notification process. Best practice: list all PRs included, credit all contributors by name and PR number, post to both product and engineering channels.

### 3. Communications

- [ ] Reply to any unanswered threads from today.
- [ ] Post end-of-day status updates.
- [ ] Send motivational or acknowledgment messages to contributors.

### 4. Lessons Learned

- [ ] Document any reusable lessons in `lessons/` (patterns, mistakes, solutions that apply beyond this session).
- [ ] Update project REFERENCE.md with any new stable facts discovered today.

### 5. Career Amplification

- [ ] Review today's work for content opportunities: blog posts, articles, videos, talks.
- [ ] Note ideas in a running list (see thought-leadership writing skill for the full workflow when ready to write).
- [ ] Themes to watch for: novel patterns, hard-won solutions, process innovations, team dynamics insights, industry observations.

### 6. Context Capture

- [ ] Update CONTEXT.md with day's progress and new state.
- [ ] Update MEMORY.md if current state info is stale (version numbers, environment status, team assignments).
- [ ] Update `last_session` date in `index.yaml` for each active project worked on today.
- [ ] Commit and push context changes to ai-knowledge repos.
- [ ] Push updates to any shared ai-knowledge repos if modified.

### 7. Skills Maintenance

- [ ] If any skills were edited during the session (in the installed `~/.claude/skills/` location), check whether those edits need to be synced back to the source repo. Use `synthesis-skills-manager` or check `.source.json` provenance files.
- [ ] If skills were updated in source repos, verify they were installed to the project(s) that use them.

### 8. Machine Sync

- [ ] Run mac-sync (credentials, config, git remotes across machines).

### 9. Repo Guard — Final Verification

**This step is mandatory and must be the last step before ending any session.**

- [ ] Run `repo_sync_check.py` (from `synthesis-repo-guard` skill) across the full workspace.
- [ ] If ANY repos are dirty or unpushed, resolve them before ending: commit and push, or explicitly decide to discard.
- [ ] Zero untracked files, zero uncommitted changes, zero unpushed commits. No exceptions.

This is not the same as steps 6-8. Those steps commit specific known changes. This step is the **verification gate** that catches anything those steps missed — files from earlier in the session, changes in repos you forgot about, skills edited in `~/.claude/skills/` that weren't synced back. The gate must pass before the session ends.

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
2. **On completion of any significant task**, play the audio alert:
   ```bash
   afplay /System/Library/Sounds/Glass.aiff && \
   afplay /System/Library/Sounds/Glass.aiff && \
   afplay /System/Library/Sounds/Glass.aiff && \
   say "[User name], [task description] is complete."
   ```
3. **If a blocker requires input**, play the alert FIRST to get attention, then display the question.
4. **This is not limited to deployments** — any significant milestone (PR review posted, integration complete, deployment done, tests passing after a fix) should alert if the user is away.

**Prerequisite:** `Bash(afplay:*)` and `Bash(say:*)` must be in the user's Claude Code allowed commands. If not, warn at the start of autonomous mode.

---

## Principles Behind These Checklists

- **Dependency-ordered:** Each step feeds the next. Sync before reading. Read before planning. Plan before messaging.
- **Information entropy reduction:** The primary purpose is closing the gap between what happened and what you know.
- **Human investment:** Motivational messages are not optional — they are a force multiplier on a distributed team.
- **Career compounding:** Every day produces raw material for thought leadership. The discipline is noticing it.
- **State capture:** If you do not capture today's state, tomorrow's start takes longer. This compounds.
