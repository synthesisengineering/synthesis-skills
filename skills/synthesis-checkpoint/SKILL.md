---
name: synthesis-checkpoint
description: "Mid-session refresh and drift-recovery protocol. Re-syncs the agent's awareness of current date, project state, recent commit history, and concurrent root-session claims. Use when asked to: checkpoint, re-sync, refresh context, mid-session refresh, recover from compaction, re-read project state, verify dates, drift check, coordination check, where are we, what was last done, am I caught up. Invoke on any suspicion of context drift, after long conversation pauses, before generating time-interval claims, or before writes when another agent session is active."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.5.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Checkpoint — Mid-Session Refresh & Drift Recovery

## The Problem

LLMs are stateless at the model level. Across a long conversation, an LLM's sense of "what's true now" can drift from what's actually on disk and in git. Drift sources:

- **Time drift.** The model has no clock. If the conversation started Tuesday and continues Wednesday, the model often still thinks it's Tuesday.
- **State drift.** Project CONTEXT.md may have been edited (by user, by sub-agent, by another session) since the model last read it.
- **Compaction drift.** When the context window approaches its limit, the harness may summarize older turns. Details disappear. The model often cannot detect that this happened.
- **Cached-fact drift.** Facts the model read earlier in the conversation (last commit, last session date, last decision) may no longer be true.
- **Coordination drift.** Another live root session may have claimed or changed
  the same source area since the last tool call.

Self-discipline degrades with conversation length. Rules read at session start lose salience as turns accumulate. Even a model that "knows" to verify often skips verification under the weight of accumulated context.

This skill is the recovery primitive. It is a tight, low-friction protocol the agent runs on demand or on a detected drift signal — and the act of running it restores ground truth.

## When To Invoke

Invoke synthesis-checkpoint when any of these conditions fire:

**Triggered by the user:**
- User asks "where are we?" / "what's the status?" / "what's been done?"
- User asks the agent to continue work after a pause
- User says "remember to..." or "you forgot..."
- User indicates the agent has drifted ("that's not right", "you said earlier...", "actually...")
- User invokes this skill by name or by keyword (checkpoint, re-sync, refresh)

**Triggered by the agent's own self-monitoring:**
- Before generating any time-interval claim ("N days ago", "yesterday", "last session", "this week")
- Before quoting any project status from cached memory
- After at least 10 minutes between user turns when the client exposes message
  timestamps. Ten minutes is the default freshness boundary: long enough to
  avoid checkpointing ordinary back-and-forth, short enough to catch another
  client session changing shared state. If timestamps are unavailable, any
  resume/continue phrasing after an apparent pause triggers the checkpoint.
- After ~25 substantive tool calls, regardless of perceived need
- When the model says or thinks "I don't recall" about a recent decision
- When a file read reveals content the model didn't expect (state drift signal)
- When the user references a decision the model has no record of (compaction signal)
- When resuming work on a project after working on something else in the same session
- When the shared coordination board changes or another root session becomes active

**Triggered automatically by lifecycle hooks:**

- SessionStart runs an equivalent of this skill's initial steps.
- Codex `PostCompact` reloads the active project and controlling plan.
- Stop can detect long sessions and emit a re-sync reminder.
- PreToolUse can inject verified time before time-sensitive operations.

## The Protocol

Steps run in order. Each step is one shell or file operation; total cost is ~6 tool calls.

### Step 0 — Read cross-agent coordination

If `~/.synthesis/coordination/active-sessions.md` exists, read it before any
write. Confirm that this session's claimed area still covers the intended
files, read new messages addressed to this session, and stop writes on any
overlap. Add or refresh claims with the
`synthesis-project-management/scripts/coordination.py` helper.

### Step 1 — Verify current time

```bash
date "+%Y-%m-%d %H:%M:%S %Z (%A)"
```

Read the output. Set this as your authoritative "current time" anchor. Compare to whatever you previously believed about the current time. Note any difference larger than a few minutes — that's drift, and it means in-context time impressions are unreliable.

### Step 2 — Verify project state from disk

Identify the active project. Typically the one whose `CONTEXT.md` is in the current working directory or was most recently mentioned.

Read its files in this order:
1. `CONTEXT.md` — current state, what's next, recent sessions
2. The latest entry in `sessions/YYYY-MM.md` (whichever monthly file is most recent)
3. `REFERENCE.md` (full file or section-skim, depending on size)

Note the "Last session" header in CONTEXT.md. Do not trust it as authoritative — it is a cache. Treat it as a starting hypothesis to verify in Step 3.

### Step 3 — Verify project history from git

```bash
git log -10 --pretty=format:"%h %ai %s" -- <project-path>
```

Read the most recent ~10 commit timestamps and subjects. This is the source of truth for "what happened when in this project."

Cross-check against CONTEXT.md's "Last session" claim:
- If CONTEXT.md's "Last session" date matches the most recent project-touching commit's date — proceed; the cache is fresh.
- If CONTEXT.md's "Last session" date is OLDER than the most recent commit — CONTEXT.md is stale; the most recent commit's date is the real "last session." Note the discrepancy.
- If CONTEXT.md's "Last session" date is NEWER than the most recent commit — uncommitted work exists OR the date in CONTEXT.md was written incorrectly. Run `git status` to disambiguate.

### Step 4 — Cross-reference tasks and recent decisions

If the client provides an in-session task or plan surface, read it. Treat that
as the third source of truth—ephemeral session memory to compare against disk
and git.

If there's a planning artifact (a plan file, a design doc, a checklist) referenced from CONTEXT.md — re-read it.

### Step 5 — Reconcile and report

Before reporting, if `synthesis-agent-conformance` is installed, run its
`hook-live`, `catalog`, and `instruction-budget` modes against the current
source/repository. The unqualified `hook-live` result is current global health.
If the durable release or handoff record names accepted Claude and Codex
session UUIDs, also run `hook-live` with
`--claude-receipt-session-id` and `--codex-receipt-session-id`. Report the two
scopes separately: a newer unrelated receipt can fail current health without
revoking preserved accepted evidence, while an exact-session failure means the
record can no longer be reverified from live artifacts. Never replace the
current-health result with the selected historical result.

Compare this task's own SessionStart receipt plugin version with current source
and installed truth. A mismatch means this task has a stale startup registry.
Save the durable checkpoint, then use a receipt-based recovery ladder:

1. Ask the user to restart the current agentic client and resume this same
   root conversation when that client can rehydrate an existing task.
2. After restart, require a genuine transcript-bound SessionStart event for
   the same root-session UUID, current plugin version, and enabled immutable
   plugin root; also confirm the loaded skill metadata matches installed
   truth.
3. Continue in the same conversation when all of those checks pass. The
   process restart is a genuine lifecycle reload even though the transcript
   identity is preserved.
4. Require a new Claude Code conversation or Codex task only when restart is
   unsupported, the same-session receipt is absent or mismatched, the
   transcript identity changes unexpectedly, or the loaded registry remains
   stale.

Installing or copying a cache in place is not itself a reload. The evidence
comes from the subsequent client lifecycle event, not from the installer.

In one short paragraph in the next response to the user, state:
- Today's verified date and time
- The project's verified "last session" date (from git log)
- Where the agent's mental state diverged from disk/git, if anywhere
- What the agent will do next, grounded in the verified facts
- Current coordination claim and any conflict or new inter-session message

Show this verification step in the response. It is the L4 visible-verification mechanism from the synthesis-context-temporal-continuity project — the user must be able to see that the checkpoint ran and what it produced.

### Step 6 — Update CONTEXT.md if it was stale

If Step 3 revealed CONTEXT.md was out of date (later commits exist that aren't reflected in its "Last session" or "Recent Sessions" sections), update CONTEXT.md in place to reflect verified facts. Leave the correction session-attributed and locally receipted; publish it in the next explicit remote handoff or day-end batch. This prevents the next local client from inheriting the stale cache without creating a network round trip at every checkpoint.

## Output Format

The agent's response after invoking this skill should include something like:

> **Checkpoint complete.** Verified facts:
> - Today: 2026-05-27 10:49 EDT (Wednesday)
> - Last project commit: 2026-05-26 12:47 EDT (commit `51b8e6d`, "Maintain context: refresh inbox-cleanup CONTEXT.md")
> - Interval since last session: ~22 hours
> - CONTEXT.md "Last session" matched git log — cache was fresh
> - In-progress task: [task summary from the client task/plan surface]
>
> Proceeding with [next action].

If discrepancies were found:

> **Checkpoint complete — drift detected.** Verified facts:
> - Today: 2026-05-27 10:49 EDT
> - CONTEXT.md said: "Last session: 2026-05-18 (PM)"
> - Git log said: most recent project commit is 2026-05-26 ("re-verification sweep")
> - Interpretation: CONTEXT.md was mis-labeled; the May 26 sweep was the real last session.
> - Action: updating CONTEXT.md with corrected dates before continuing.

## What Counts as "Substantive Work"

Trigger the checkpoint protocol BEFORE these kinds of work, not after:

- Writing a session-log entry
- Computing or claiming a time interval ("X days ago", "yesterday", "this week")
- Quoting project status to the user
- Making a planning decision based on "where we left off"
- Generating a commit message that mentions dates or intervals

After-the-fact verification catches some errors but lets stale facts propagate into outputs first. Verifying first is cheaper than correcting later.

## Relationship to Other Synthesis Skills

This skill is the recovery primitive that other skills delegate to:

- **synthesis-context-lifecycle** — references this skill in its Session Start Protocol and Mid-Session Refresh Protocol. The lifecycle skill defines the architecture of CONTEXT.md / REFERENCE.md / sessions/; this skill is the per-invocation drift-check.
- **synthesis-daily-rituals** — references this skill in its day-start ritual. Day-start always runs a checkpoint before any project work begins.
- **synthesis-project-management** — references this skill in its project-discovery protocol. When the user mentions a project, the agent runs a checkpoint on that project's files.

These skills are independent. Each works standalone. But they are stronger when they all delegate the drift-check to this single skill, which guarantees a consistent protocol.

## Why This Works

The synthesis project management system already has the durable layer (CONTEXT.md, REFERENCE.md, sessions/, git history). The failure mode is not lack of data — it's the agent's in-context memory drifting from that data over time. This skill's only job is to force a re-sync against the durable layer at the moments when it matters most.

It is intentionally lightweight (~5 tool calls), intentionally codified (no variation between invocations), and intentionally visible (the user sees the verification step). All three properties matter:

- **Lightweight** — runs without the agent rationalizing "this isn't worth the steps"
- **Codified** — runs the same way every time, so users can recognize when it ran and when it didn't
- **Visible** — users can spot when verification was skipped and intervene early

This is the **NTP** of the synthesis project management system: periodic, authoritative-source-driven, automatic.
